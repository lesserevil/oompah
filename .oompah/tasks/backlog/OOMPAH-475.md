---
id: OOMPAH-475
type: feature
status: Backlog
priority: 1
title: Dispatch, retry, and recover independent auditor agents
parent: OOMPAH-458
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:06:15.927352Z'
updated_at: '2026-07-28T13:06:15.927352Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add a priority audit lane that reads persisted In Validation requests, gathers target-specific evidence, selects an independent candidate, claims the task/epic branch, and starts the reserved auditor focus. Auditors consume the normal global concurrency limit and serialize with implementation workers on the same task or epic branch. Persist running attempt identity before launch. On transient provider/tool failure, rotate candidates with normal backoff up to OOMPAH_AUDIT_MAX_ATTEMPTS. Rehydrate pending/running attempts on restart, detect abandoned auditor sessions, and retry idempotently. If every independent candidate is exhausted, submit the no-independent-auditor failure so the coordinator moves to Needs Human with configuration instructions.

Tests

Cover priority versus ordinary Open work, concurrency limit, one-agent-per-epic serialization, successful result, candidate rotation, rate limit, timeout, crash, restart, abandoned claim, changed fingerprint during run, stale result, max attempts, no candidates, and actionable final comment. Run focused scheduler tests and make test.

Acceptance criteria

Every eligible persisted audit is eventually dispatched once, retried safely, or moved to actionable Needs Human; auditor work never races a branch writer or exceeds configured global concurrency.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

