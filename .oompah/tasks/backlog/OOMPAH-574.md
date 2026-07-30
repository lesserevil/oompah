---
id: OOMPAH-574
type: task
status: Backlog
priority: null
title: Rerun failed cached quality gates on explicit same-head retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:15:22.112289Z'
updated_at: '2026-07-30T02:15:22.112289Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Make explicit integration resubmission invalidate and re-execute cached BranchQualityGate outcomes whose prior result is failed, timed_out, or error, even when the pushed head SHA is unchanged. Continue reusing passed evidence for the exact head, keep interrupted runs non-persistent, and prevent duplicate concurrent gates for one row/head. Wire the retry intent through the task handoff/API and integration executor without weakening normal cache reuse. Relevant files: oompah/quality_gate.py, oompah/integration_queue.py, oompah/server.py, and oompah/integration_executor.py.

Tests

Add regression coverage in tests/test_quality_gate.py, tests/test_integration_queue.py, and task-handoff/integration-executor tests for explicit same-SHA retry after failure, timeout, and error; passed-result reuse; interruption behavior; and concurrent retry deduplication. Run focused tests and the configured full Makefile gate.

Acceptance criteria

An explicit retry of an unchanged blocked integration row performs a real fresh quality gate instead of immediately reusing failed evidence; successful evidence remains safely reusable and no duplicate active gate is started.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

