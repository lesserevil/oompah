---
id: OOMPAH-488
type: task
status: Backlog
priority: 1
title: Validate the complete task Done-Merged-Archived audit lifecycle
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-476
- OOMPAH-477
- OOMPAH-479
- OOMPAH-481
- OOMPAH-484
- OOMPAH-485
- OOMPAH-486
- OOMPAH-487
labels: []
assignee: null
created_at: '2026-07-28T13:08:27.238658Z'
updated_at: '2026-07-28T13:10:07.780492Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Create an end-to-end Git fixture and fake provider/SCM setup for one implementation task. Dispatch a worker with provider/model A, commit/push work, request Done, assert In Validation, dispatch provider/model B auditor, submit PASS, assert Done and review creation. Simulate correct review merge, assert a separate Merged audit with completion prerequisite, pass it, then age the task and pass a safe-retirement Archived audit. Assert durable comments/metadata, API summaries, metrics, state-branch commits, and restart recovery between at least two stages. Add failure variants for incomplete work, failed CI, wrong merge target, and unsafe archive.

Tests

This task is the test implementation. Keep fixtures deterministic and offline; do not call real providers or forges. Run the new test file repeatedly, relevant existing integration suites, and make test.

Acceptance criteria

The automated scenario proves three different auditors/contracts occur in order, the worker never self-certifies, each failure returns to the documented repair state, and state remains correct across restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

