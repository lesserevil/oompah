---
id: OOMPAH-919
type: bug
status: In Progress
priority: 1
title: Exclude paused projects from shadow rollout coverage failures
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T15:44:04.212180Z'
updated_at: '2026-08-08T15:47:00.249527Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

The live all-domain shadow rollout registers six managed projects but intentionally skips paused projects. WorkflowRuntime.reconcile currently treats every skipped binding as a coverage failure, so healthy active-project decisions can never accumulate a successful shadow sweep while any unrelated project is paused. Change oompah/workflow_runtime.py so rollout coverage is evaluated over enabled bindings only, while an empty enabled set still cannot qualify. Add a regression in tests/test_workflow_runtime.py with one enabled and one paused binding, asserting the paused project remains skipped and the active project produces a successful shadow sweep. Run focused tests and the exact full make test gate. Acceptance: paused projects neither mutate nor fail active-project rollout qualification; missing/error/incomplete enabled-project coverage still fails closed; the live rollout reaches qualification without unpausing unrelated projects.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 15:47
---
Live shadow rollout reproduced the bug on build 958fb98: two sweeps failed because paused unrelated projects were treated as missing active coverage. The direct owner fix now qualifies only enabled bindings while retaining a no-active-project fail-closed check. Focused serial regressions pass (3 tests).
---
<!-- COMMENTS:END -->
