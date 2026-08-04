---
id: OOMPAH-766
type: epic
status: In Progress
priority: 1
title: Implement durable leased workflow jobs and restart-safe sagas
parent: OOMPAH-763
children:
- OOMPAH-780
- OOMPAH-783
- OOMPAH-785
blocked_by: []
start_blocked_by: &id001
- OOMPAH-769
- OOMPAH-765
labels: []
assignee: null
created_at: '2026-08-04T13:55:56.148047Z'
updated_at: '2026-08-04T15:30:56.235007Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Add a durable workflow-job ledger for execution ownership and recovery. Each job records stable ID/idempotency key, project/task/generation, action/phase, expected evidence/head, queued/leased/running/retry-wait/completed/superseded/action-required state, lease owner/expiry, attempt budget, next retry, timestamps, checkpoint, and categorized failure. Implement a resumable saga: persist intent, lease, revalidate preconditions, perform external effect, verify, checkpoint, request transition, complete. Every step must be idempotent and safe across process death because tracker/Git/forge/SQLite cannot share one transaction. Build a durable consumer, expired-lease recovery, bounded backoff, explicit exhaustion, and observability. Replace process-local lifecycle authority/future ownership only as each domain migrates. Required tests: concurrent claimers, exact-generation fencing, kill/restart injection after every persistence boundary, external effect succeeds before crash, tracker write succeeds before acknowledgment, lease expiry/reclaim, retry exhaustion, and cross-project isolation. Acceptance: no workflow action relies solely on a process-local map/future/timestamp; every unfinished job resumes, supersedes, or explicitly escalates after restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

