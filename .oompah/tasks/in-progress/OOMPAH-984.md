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
updated_at: '2026-08-10T04:30:04.614266Z'
work_branch: OOMPAH-984
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/792
review_number: '792'
review_head: 7c53bf19484e8f65cd0a8c6f69df4c8270771e33
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
oompah.review_url: https://github.com/lesserevil/oompah/pull/792
oompah.review_number: '792'
oompah.target_branch: main
oompah.review_head: 7c53bf19484e8f65cd0a8c6f69df4c8270771e33
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
author: oompah
created: 2026-08-10 03:59
---
Validation on pushed commit 7c53bf19484e8f65cd0a8c6f69df4c8270771e33: Python 3.13.11 focused regression passed 25 consecutive runs; Python 3.13 workflow-worker suite passed 49/49; Python 3.12.12 focused compatibility passed; git diff --check passed. Focused Ruff reports only the pre-existing import-order finding in tests/test_workflow_worker.py, outside this diff. Review approved the test-only lifecycle-barrier change; production code is unchanged.
---
author: oompah
created: 2026-08-10 04:10
---
Branch quality gate passed for `7c53bf19484e8f65cd0a8c6f69df4c8270771e33` using `make test` in 164.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-10 04:30
---
Direct-owner CI repair rebased PR #792 onto exact OOMPAH-985 commit 2a255c5c0d2f8d9850c4135809422c33f9409571 (which also includes merged OOMPAH-983). Range-diff preserved the OOMPAH-984 patch exactly at new head 6473c14fdf8e148472c917ec3f1695c98713f074; combined workflow-worker and release-refresh suites pass 104/104. Remote and PR head are exact.
---
<!-- COMMENTS:END -->
