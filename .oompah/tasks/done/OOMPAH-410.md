---
id: OOMPAH-410
type: task
status: Done
priority: null
title: Redispatch resolvers when conflicted reviews remain open
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T16:24:49.141548Z'
updated_at: '2026-07-22T16:27:13.964181Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the YOLO conflict-resolution lifecycle. When a merge-conflict resolver exits without resolving an open conflicted PR/MR (including dirty-worktree or sandbox failures), leave or restore the owning task to Needs Rebase with merge-conflict and ensure it remains eligible for retry/redispatch. Do not close the task merely because the agent exited. Add regression tests for ordinary and mature epic review tasks. Acceptance criteria: an open conflicted review never remains with zero active/retry resolver after a resolver exit; the task is requeued with actionable diagnostics; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 16:27
---
Fixed resolver exit handling: when the existing open review is still conflicted, normal resolver completion now keeps the task at Needs Rebase with merge-conflict, records diagnostics, and wakes redispatch instead of treating the repair as complete. Added mature-epic regression coverage. Verification: make test passed.
---
<!-- COMMENTS:END -->
