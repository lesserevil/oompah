---
id: OOMPAH-983
type: task
status: In Progress
priority: null
title: Make reserved workflow control-capacity proof deterministic on Python 3.13
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T03:38:07.660153Z'
updated_at: '2026-08-10T03:38:38.278987Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by OOMPAH-982 protected PR #790, GitHub Actions run 31352693288. Python 3.11 and 3.12 passed all 19,297 tests, while Python 3.13 timed out in tests/test_workflow_runtime.py::test_long_delivery_cannot_block_control_jobs_or_projection_generations waiting for validation_submission after the long standalone delivery and authority_revocation. This is an unrelated loaded-scheduler test race: the proof relies on real worker scheduling reaching an event inside a fixed timeout rather than a deterministic admission/completion barrier. Scope: make the regression deterministically synchronize exact shared-lane delivery, reserved control-slot authority_revocation, subsequent validation_submission admission, and projection-generation advancement; preserve production max_concurrent/control_reserved_slots behavior and do not merely widen sleeps/timeouts. Relevant files: tests/test_workflow_runtime.py and only narrow WorkflowRuntime/DurableWorkflowWorker seams if a reproducer proves production changes necessary. Required tests: reproduce under Python 3.13/two xdist workers or repeated focused load; the test fails if reserved control work cannot progress, proves delivery remains leased, both control effects finish in order, projections advance, and no effect duplicates; run the workflow-runtime suite and Ruff/diff checks. Acceptance: repeated focused runs are deterministic and protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

