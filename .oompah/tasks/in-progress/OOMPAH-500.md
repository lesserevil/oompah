---
id: OOMPAH-500
type: task
status: In Progress
priority: 1
title: Measure the pruned suite and enforce the no-network final gate
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-492
- OOMPAH-493
- OOMPAH-494
- OOMPAH-495
- OOMPAH-496
- OOMPAH-497
- OOMPAH-498
- OOMPAH-499
labels: []
assignee: null
created_at: '2026-07-28T13:53:35.430103Z'
updated_at: '2026-07-28T16:50:18.909612Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 99872f39-7d3d-4145-9d63-0acae7d74834
oompah.work_branch: epic-OOMPAH-490
---
## Summary

Implementation scope

Validate the completed pruning epic from a clean checkout after every other child is merged. Run collection-only and timed full-suite baselines using the Makefile test target with duration reporting. Confirm the Git-remote safety barrier by tracing child Git commands or using the guard's own audit mechanism; no command may attempt a network URL, and all actual pushes must target temporary local bare remotes. Check for leaked Granian/server/git child processes after the run. Compare module count, collected cases, wall-clock time, slowest cases, skips/xfails, and failures with the July 28 baseline: 282 modules, about 201,700 lines, 12,347 collected tests; the interrupted timing sample had 5,954 passes in 309.78 seconds. Do not weaken thresholds or delete a failing test to make the report pass.

Tests

This task is the final test gate. Run `make test` at least once from a clean checkout and repeat the newly consolidated Granian and safety suites to check determinism. Run `git status` afterward.

Acceptance criteria

The complete suite passes, the checkout and tracker are unchanged, zero network Git operations occur, zero test-owned subprocesses remain, collected cases are reduced by the expected pruning, the slowest known isolation defects no longer take network-scale time, and a concise before/after measurement is posted as the task completion summary.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 16:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:50
---
Understanding: I am screening OOMPAH-500 for duplicate work before implementation. I will search the task/docs corpus for the pruning, suite-measurement, Granian, and no-network Git safety scopes, then read each plausible candidate task and comments in full. If no duplicate is confirmed, I will record the closest reviewed tasks and hand off to the next implementation focus without changing code.
---
<!-- COMMENTS:END -->
