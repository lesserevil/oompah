---
id: OOMPAH-908
type: task
status: Backlog
priority: null
title: Give the whole-corpus dispatch contract scan a load-safe deadline
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T07:51:47.950793Z'
updated_at: '2026-08-08T07:51:47.950793Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Recurrence after completed OOMPAH-851 on exact systemic head 6cbbd6ef7: the full make test gate passed 18,485 tests and then tests/test_tick_dispatch_mock_contract.py::test_tick_dispatch_replacements_use_faithful_helper hit the global 5-second timeout while walking an unrelated module AST under saturated xdist load. There was no contract violation; the architectural scan is deliberately whole-corpus and its runtime grows with the test tree. Implementation scope: give this bounded corpus-wide architectural test a deterministic scoped deadline appropriate for saturated full gates, or further optimize the fail-closed prefilter without weakening direct, dynamic, decoded f-string, arbitrary split-string, malformed-source, helper-shadow, or missing-import detection. Do not change the global timeout or production telemetry. Required tests: exact architectural module repeatedly and under xdist/load, retain all fail-closed prefilter regressions, and rerun the exact full make test gate on the repaired composed head. Acceptance: the corpus scan cannot fail solely because the host is saturated, still reports every forbidden _handle_dispatch_needed replacement, and no global timeout is widened.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

