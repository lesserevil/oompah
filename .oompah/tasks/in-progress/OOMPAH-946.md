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
updated_at: '2026-08-09T09:36:47.246102Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Hosted CI run 31305502103 on reviewed OOMPAH-939 head b1fc26aa passed the complete Python 3.11 and 3.12 gates but failed Python 3.13 only in tests/test_native_validation_guard.py::test_detached_heavy_descendant_retains_native_capacity_until_exit: the wrapper-created detached descendant PID disappeared before the post-lease assertion. This test and its production lease watcher are the regression contract delivered by OOMPAH-841; no OOMPAH-939 code touches them. Scope: reproduce the Python 3.13/hosted-runner timing, determine whether the native wrapper/watch process prematurely terminates or the test observes before detached process readiness, and repair the production lifetime fence or deterministic test handshake as evidence requires. Do not relax the invariant that heavyweight descendants retain native capacity until their exact process generation exits, and do not replace PID/start-tick fencing with a sleep. Required tests: deterministic wrapper-exit/detached-child readiness handshake, descendant survives parent exit while lease remains held, PID reuse and genuine early-exit behavior, Python 3.11-3.13 focused matrix, terminal mutation/secret scans, and complete make test. Acceptance: repeated hosted matrix runs no longer fail this contract and exact lease capacity remains held for every live detached heavyweight descendant.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

