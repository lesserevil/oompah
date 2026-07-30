---
id: OOMPAH-600
type: task
status: Backlog
priority: 1
title: Integrate OOMPAH-581 and prune current safe terminal workspaces
parent: OOMPAH-588
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-598
labels: []
assignee: null
created_at: '2026-07-30T14:15:58.634342Z'
updated_at: '2026-07-30T14:17:34.729739Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Triggered by: OOMPAH-581

Implementation scope

Use the existing OOMPAH-581 implementation for task-style branches/worktrees created under terminal epic repair flows. Deliver it through the normal full gate and terminal audit, deploy it, then run cleanup and verify current safe merged/archived artifacts are removed. Preserve TASK-472, TASK-473, TASK-495-ci and every dirty or default-unreachable head; do not use destructive broad paths or direct task-file edits.

Tests

Retain OOMPAH-581 tests, add any live-shape reproducer needed, run make test, and record before/after worktree/local/remote branch counts with categorized preserved reasons.

Acceptance criteria

OOMPAH-581 reaches Merged; safe terminal epic repair artifacts are gone; dirty/unmerged work remains byte-for-byte intact and registered; cleanup reports no error.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:17
---
Coordination: OOMPAH-598 owns delivery of OOMPAH-581. This task hard-starts after OOMPAH-598 and owns only deployment verification plus live safe cleanup/pruning; do not independently open or merge a second OOMPAH-581 delivery path.
---
<!-- COMMENTS:END -->
