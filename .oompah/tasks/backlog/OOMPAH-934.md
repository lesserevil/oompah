---
id: OOMPAH-934
type: task
status: Backlog
priority: null
title: Make concurrency regressions deterministic on constrained CI hosts
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T06:26:17.775582Z'
updated_at: '2026-08-09T06:26:17.775582Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Problem: after OOMPAH-933 made protected GitHub CI run the supported Makefile gate, all Python 3.11/3.12/3.13 jobs exposed deterministic test-harness races on ubuntu-24.04. Tests assume broker lease cleanup is instantaneous after a child exits, use fixed sleeps before an orchestrator startup tick begins, reuse GitHubProvider's production class-level PR detail cache across unit tests, treat a just-created PID file as fully written, and impose pytest's 5-second default around multiprocess checks whose own subprocess contracts allow 10 seconds. Scope: make the affected tests synchronize on observable events/state, isolate shared cache state, wait for complete PID publication, and assign narrow timeouts consistent with each test's bounded subprocess contracts; keep production safety behavior and the global timeout fail-closed. Relevant files: tests/test_native_validation_guard.py, tests/test_scm.py, tests/test_tick_lane_serialization.py, tests/test_terminal_audit_scanner.py, tests/test_validation_resource_lease.py, and only production code if a focused reproducer proves it necessary. Required tests: repeatedly run the exact previously failing tests under supported Python versions and the parallel runner, then run make test. Acceptance: the tests make no correctness decision from an arbitrary sleep or unisolated class cache; native lease assertions wait for the broker's documented eventual release; all PR #749 Python 3.11/3.12/3.13 checks pass without relaxing product invariants or branch protection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

