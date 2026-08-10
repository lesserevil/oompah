---
id: OOMPAH-992
type: bug
status: Backlog
priority: 1
title: Bound task creation when quality-gate reconciliation owns project mutation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:32:43.695792Z'
updated_at: '2026-08-10T10:32:43.695792Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-991

While filing OOMPAH-991 immediately after OOMPAH-989's submitted branch quality gate failed, two authenticated oompah task create requests remained blocked for more than three minutes. The HTTP control plane and health endpoint stayed responsive, but three server request threads remained on the same futex-backed synchronization point; cancelling both clients did not cancel the accepted server work, and an identity-checked emergency restart was required. After restart, the same create completed in 5.35 seconds. Diagnose project task-mutation serialization across quality-gate result reconciliation, issue snapshot refresh, durable workflow effects, and client disconnect/cancellation. Add deterministic barriers that hold the gate-result/status path while one or more task creates arrive, prove bounded completion or retryable failure, ensure cancelled duplicate clients cannot create duplicate tasks later, and ensure no lock is held across tracker/SCM/network callbacks. Acceptance: task creation cannot wait indefinitely behind gate reconciliation; accepted work has idempotent identity and observable completion; restart recovery converges without duplicates; focused concurrency/restart tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

