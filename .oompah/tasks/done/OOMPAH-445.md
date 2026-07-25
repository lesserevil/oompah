---
id: OOMPAH-445
type: task
status: Done
priority: null
title: Keep shared-epic prompt branch aligned with allocated workspace
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-25T20:24:30.180505Z'
updated_at: '2026-07-25T20:38:48.143198Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Bug observed while recovering EXOCOMP-115: the child already had correct work_branch=epic-EXOCOMP-110 but a stale branch_name=EXOCOMP-115. _create_workspace_for_issue only assigned issue.branch_name inside the conditional that repairs work_branch, so render_prompt told the ACP agent its shared epic worktree was on EXOCOMP-115. The session then switched the shared worktree to that per-task branch, stranding edits from the epic branch.\n\nImplementation scope: in oompah/orchestrator.py, always align the in-memory issue.branch_name to the resolved parent epic branch before rendering/dispatch, even when persisted work_branch is already correct; keep tracker writes conditional on stale work_branch. Add a regression in tests/test_epic_strategy.py covering correct work_branch plus stale/default branch_name and assert both workspace allocation and rendered branch identity use the epic branch. Check related unresolved-parent fallback for the same invariant.\n\nAcceptance criteria: shared-epic prompts never name a per-task branch; dispatch cannot switch the shared worktree away from the epic branch due to stale Issue.branch_name; no unnecessary tracker metadata write occurs when work_branch is already correct; relevant focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-25 20:26
---
Manual repair is in progress in the main checkout. Holding this task out of scheduler dispatch until the regression suite and commit complete so a second agent cannot race the same files.
---
author: oompah
created: 2026-07-25 20:38
---
Fixed shared-epic dispatch so the prompt branch is always aligned with the canonical allocated epic workspace, including unresolved-parent recovery; added regression coverage; full suite passed (12,320 passed, 7 skipped); pushed as 7a7da7704.
---
<!-- COMMENTS:END -->
