---
id: OOMPAH-984
type: task
status: Ready to Integrate
priority: null
title: Make completed-call settlement recycle proof deterministic on Python 3.13
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T03:51:51.943285Z'
updated_at: '2026-08-10T03:58:58.383689Z'
work_branch: OOMPAH-984
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-984
  head_sha: 7c53bf19484e8f65cd0a8c6f69df4c8270771e33
  submitted_at: '2026-08-10T03:58:40.365788+00:00'
  updated_at: '2026-08-10T03:58:40.365788+00:00'
oompah.work_branch: OOMPAH-984
---
## Summary

Triggered by OOMPAH-982 protected PR #790, GitHub Actions run 31352693288 attempt 2, job 93347765590. Python 3.13 timed out in tests/test_workflow_worker.py::test_completed_call_settlement_store_failure_requests_safe_recycle while waiting for the safe recycle request after a simulated transient settle_quarantined_call store failure; Python 3.11/3.12 and the exact local branch gate passed. Scope: reproduce and remove the scheduling race using exact durable call-settlement/recycle synchronization, changing production workflow worker/store behavior only if the reproducer proves a real correctness gap; do not widen sleeps or timeouts. Relevant files: tests/test_workflow_worker.py and narrow oompah/workflow_worker.py or durable store seams if needed. Required tests: repeated focused runs on Python 3.13 under load, workflow-worker suite, Python 3.12 focused compatibility, Ruff/diff checks. Acceptance: the test deterministically proves a completed quarantined call whose settlement store write fails requests exactly one safe recycle and preserves late-effect fencing, without relying on scheduler timing; protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 03:58
---
Replaced the flaky 0.5-second recycle-observer deadline with exact worker quarantine-monitor quiescence, retaining the existing exactly-once recycle and late-effect fencing assertions. No production behavior changed. Commit 7c53bf19484e8f65cd0a8c6f69df4c8270771e33 is pushed on OOMPAH-984.
---
<!-- COMMENTS:END -->
