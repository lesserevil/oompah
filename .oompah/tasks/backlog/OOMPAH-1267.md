---
id: OOMPAH-1267
type: task
status: Backlog
priority: null
title: Make restart replacement rollback test deterministic under concurrent gates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T08:43:25.263614Z'
updated_at: '2026-08-14T08:43:25.263614Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 74c46553-2c2b-43cf-a780-9f13e770c900
  request_fingerprint: c93c49f73d14f0dbd98db4eaf2f0bc6f44f4965a6f4e68ab29b4fa036d4eeecd
---
## Summary

Repeated concurrency bug: tests/test_restart_api.py::test_replacement_timeout_rolls_back_before_concurrent_replacement failed late in two independent full Makefile gates running concurrently on OOMPAH-1266 and OOMPAH-1249. Both branches are unrelated to restart lifecycle code; the exact test passes isolated and the full restart API file passes 33/33, proving the current synchronization/timeout contract is load-sensitive rather than deterministic. Diagnose the replacement-timeout/concurrent-replacement ordering and replace wall-clock/test-runner-load assumptions with explicit observable synchronization or a bounded state predicate. Preserve the production guarantee that a timed-out replacement rolls back before a concurrent replacement can acquire authority. Relevant context: tests/test_restart_api.py and restart replacement lifecycle/locking code. Required tests: deterministic interleavings for timeout-before-replacement and replacement-before-timeout, repeated/parallel execution under CPU load, no leaked lifecycle state or process, and focused restart plus full Makefile gate. Acceptance: the exact race test cannot fail solely because another quality gate is consuming the box, real ordering regressions still fail, and no timeout is simply widened to hide the race.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

