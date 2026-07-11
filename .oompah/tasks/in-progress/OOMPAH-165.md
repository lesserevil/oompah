---
id: OOMPAH-165
type: task
status: In Progress
priority: null
title: Fix shared epic landed detection before main merge
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-11T03:24:27.952153Z'
updated_at: '2026-07-11T03:25:02.054840Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f5ebdbcf-11a8-4ecb-942d-ce8538e903ba
---
## Summary

Bug: in shared/stacked epic workflows, oompah can mark a top-level epic Merged after child epics merge into the shared epic branch, even when that shared epic branch has not been merged to the project's default branch. Fix landed-epic detection to verify the merged PR target matches the epic's resolved target branch, add regression tests, and repair the coroot project state so the remaining epic-COROOT-4 -> main integration is visible/actionable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

