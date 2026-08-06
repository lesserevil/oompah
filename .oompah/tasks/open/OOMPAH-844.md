---
id: OOMPAH-844
type: task
status: Open
priority: null
title: Isolate orchestrator maintenance unit tests from full-corpus recovery scans
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T03:00:58.832102Z'
updated_at: '2026-08-06T03:02:41.759247Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Bug: the exact combined-tree gate for OOMPAH-821 failed after 16,116 passing tests because tests/test_orchestrator_handlers.py::TestRepoHealErrorReporting::test_heal_failure_does_not_raise_from_tick invokes the real _recover_release_addendum_leases() path. That path scans the full task corpus, can exceed the global per-test timeout under xdist saturation, and leaves the intentionally failing maintenance future visible during teardown. The same systemic coupling has affected other exact-head gates. Implementation scope: isolate the repo-heal unit test from unrelated release-addendum recovery work by stubbing _recover_release_addendum_leases; give storage-backed orchestrator construction tests an explicit bounded timeout where cold-corpus startup can legitimately exceed the global 5-second default; audit adjacent _tick unit tests for the same accidental corpus dependency without weakening production timeouts or assertions. Relevant files: tests/test_orchestrator_handlers.py and tests/test_orchestrator_github_lifecycle.py; production code should change only if investigation finds a real unbounded scan. Required tests: reproduce both named tests under repeated concurrent execution, run the affected modules, and run make test at the exact review head. Acceptance: the tests remain semantically scoped, fail on their intended assertions, pass repeatedly under load, do not leak background futures at teardown, and the canonical full gate passes without raising the per-test timeout globally.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

