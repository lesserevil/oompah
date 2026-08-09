---
id: OOMPAH-946
type: task
status: In Progress
priority: null
title: Remove detached native-validation descendant lifetime race
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:36:17.757446Z'
updated_at: '2026-08-09T10:20:27.386343Z'
work_branch: OOMPAH-946
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
  task_branch: OOMPAH-946
  head_sha: 8e2527b74e958127861621fdbcebb627d0929e24
  submitted_at: '2026-08-09T10:20:15.445451+00:00'
  updated_at: '2026-08-09T10:20:15.445451+00:00'
oompah.work_branch: OOMPAH-946
---
## Summary

Hosted CI run 31305502103 on reviewed OOMPAH-939 head b1fc26aa passed the complete Python 3.11 and 3.12 gates but failed Python 3.13 only in tests/test_native_validation_guard.py::test_detached_heavy_descendant_retains_native_capacity_until_exit: the wrapper-created detached descendant PID disappeared before the post-lease assertion. This test and its production lease watcher are the regression contract delivered by OOMPAH-841; no OOMPAH-939 code touches them. Scope: reproduce the Python 3.13/hosted-runner timing, determine whether the native wrapper/watch process prematurely terminates or the test observes before detached process readiness, and repair the production lifetime fence or deterministic test handshake as evidence requires. Do not relax the invariant that heavyweight descendants retain native capacity until their exact process generation exits, and do not replace PID/start-tick fencing with a sleep. Required tests: deterministic wrapper-exit/detached-child readiness handshake, descendant survives parent exit while lease remains held, PID reuse and genuine early-exit behavior, Python 3.11-3.13 focused matrix, terminal mutation/secret scans, and complete make test. Acceptance: repeated hosted matrix runs no longer fail this contract and exact lease capacity remains held for every live detached heavyweight descendant.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:20
---
Diagnosis confirmed from hosted run 31305502103 attempt 1: competing lease acquisition timed out even though /proc for the recorded PID vanished, so the production inherited-descriptor fence remained held. The test recorded the transient setsid launcher via $!, which may fork when it is already a group leader. Commit 8e2527b74 makes the detached inner Bash publish $BASHPID after session creation, waits for that readiness before wrapper exit, verifies exact start ticks/PGID/SID, and cleans up via exact-generation termination. Verification: 11 targeted lifecycle/PID tests, 634 complete native guard+lease tests, focused Python 3.11/3.12/3.13 matrix, repeated regression runs, Ruff, mutation scan, and secret scan passed. Full make test passed the changed regression and 18,890 other tests, then hit unrelated real-clock waiter-priority flake tracked as OOMPAH-949; that isolated test passed 20 immediate reruns.
---
author: oompah
created: 2026-08-09 10:20
---
Removed the detached descendant regression's transient setsid PID race by introducing an inner-shell readiness handshake, exact process-generation/session assertions, and exact-generation cleanup without weakening native capacity fencing. Commit 8e2527b74 is pushed. Python 3.11-3.13 focused matrix and 634 native guard/lease tests pass; full gate passed OOMPAH-946 and exposed separate OOMPAH-949.
---
<!-- COMMENTS:END -->
