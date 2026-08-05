---
id: OOMPAH-838
type: bug
status: Backlog
priority: 1
title: Preserve forced quality-gate retry through integration claim
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:45:03.282492Z'
updated_at: '2026-08-05T16:45:03.282492Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression from OOMPAH-523: an explicit same-head resubmission correctly calls IntegrationQueueStore.enqueue(... explicit_retry=True) and persists retry_forced=1, but claim_next clears retry_forced before returning the claimed IntegrationQueueItem. Orchestrator._execute_integration_item therefore always passes retry_forced=False to BranchQualityGate, reuses the prior cached failed result, and immediately routes a locally verified clean head back to Needs CI Fix. The cached failure for 9ea2b5523 is a 48.94-second truncated 9%-progress run containing only PASS lines; OOMPAH-523's immediately preceding official make test passed 15,452 tests. Implementation scope: carry one-shot force-retry authority on the claimed item while atomically clearing the durable pending flag so restarts do not loop; distinguish consumed retry intent from stored ready state and preserve exact owner/head fencing. Relevant files: oompah/integration_queue.py, oompah/orchestrator.py integration claim/execution, quality-gate cache tests. Required tests: blocked same-head explicit retry bypasses a cached failed/timed-out/error result exactly once; claimed item exposes the consumed force flag while the persisted integrating row no longer advertises a pending retry; crash/recovery does not loop; normal/new-head claims remain unforced; OOMPAH-523 regression. Acceptance: an explicit same-head resubmission executes a fresh exact gate instead of replaying cached failure, and a passing gate can integrate naturally without manual cache deletion or fake commits.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

