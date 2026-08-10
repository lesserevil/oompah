---
id: OOMPAH-984
type: task
status: In Progress
priority: null
title: Make completed-call settlement recycle proof deterministic on Python 3.13
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T03:51:51.943285Z'
updated_at: '2026-08-10T03:52:12.356536Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by OOMPAH-982 protected PR #790, GitHub Actions run 31352693288 attempt 2, job 93347765590. Python 3.13 timed out in tests/test_workflow_worker.py::test_completed_call_settlement_store_failure_requests_safe_recycle while waiting for the safe recycle request after a simulated transient settle_quarantined_call store failure; Python 3.11/3.12 and the exact local branch gate passed. Scope: reproduce and remove the scheduling race using exact durable call-settlement/recycle synchronization, changing production workflow worker/store behavior only if the reproducer proves a real correctness gap; do not widen sleeps or timeouts. Relevant files: tests/test_workflow_worker.py and narrow oompah/workflow_worker.py or durable store seams if needed. Required tests: repeated focused runs on Python 3.13 under load, workflow-worker suite, Python 3.12 focused compatibility, Ruff/diff checks. Acceptance: the test deterministically proves a completed quarantined call whose settlement store write fails requests exactly one safe recycle and preserves late-effect fencing, without relying on scheduler timing; protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

