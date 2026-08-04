---
id: OOMPAH-780
type: feature
status: Ready to Integrate
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
updated_at: '2026-08-04T15:40:55.421306Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-780
  head_sha: 713c0cbadc9f06797498f8a8bf65e73452e4ed86
  submitted_at: '2026-08-04T15:40:50.075520+00:00'
  updated_at: '2026-08-04T15:40:50.075520+00:00'
---
## Summary

Create a SQLite workflow-job ledger with migrations and typed repository. Persist job/idempotency identity, project/task/generation, action/phase, expected evidence/head, state, lease owner/expiry, attempts/max, retry time, failure category, checkpoint, timestamps, and result transition. Implement atomic enqueue, claim, renew, complete, fail/retry, supersede, cancel, expired/abandoned recovery, and bounded scans. Required tests: concurrent claimers, deterministic ordering/fairness, exact generation, lease expiry, retries/exhaustion, idempotent enqueue, restart persistence, schema upgrade, and cross-project isolation. Acceptance: store primitives alone cannot lose, duplicate-own, or revive superseded workflow work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 15:40
---
Implemented a domain-neutral SQLite workflow-job ledger with immutable project-scoped idempotency, exact project/task/generation/action filters, deterministic priority/availability/FIFO claims, opaque token-fenced leases, renew/checkpoint/complete/fail-retry operations, bounded expired/abandoned recovery, terminal supersede/cancel semantics, append-only events, and v1-to-v2 schema migration. Added 30 focused tests covering concurrent enqueue/claim, lease loss/reclaim, retry exhaustion, restart persistence, schema upgrade, bounded scans, and cross-project isolation. Verification: 195 focused/adjacent tests passed; ruff check/format, make terminal-audit-scan, staged secret scan, and diff check passed.
---
author: oompah
created: 2026-08-04 15:40
---
Implemented and verified the durable workflow-job store; exact commit 713c0cbadc9f06797498f8a8bf65e73452e4ed86 is ready to land on epic-OOMPAH-766.
---
<!-- COMMENTS:END -->
