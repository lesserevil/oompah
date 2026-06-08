---
id: TASK-469.2
title: Budget auto-archive and worktree cleanup maintenance
status: Done
assignee:
  - oompah
created_date: '2026-06-08 22:17'
updated_date: '2026-06-08 23:02'
labels: []
dependencies: []
parent_task_id: TASK-469
priority: high
ordinal: 171000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The 2026-06-08 slow tick spent 121207ms in archive work and logged hundreds of per-task archive operations, plus large terminal worktree cleanup sweeps. Move auto-archive and cleanup to incremental maintenance with a per-run budget, persisted cursor, delayed startup schedule, and separate timing/visibility. A single dispatch tick must not archive hundreds of tasks or clean every terminal worktree before returning.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Moved auto-archive and terminal worktree cleanup to delayed, bounded maintenance passes with batch-size env knobs, persisted cursors, and per-run visibility.
<!-- SECTION:FINAL_SUMMARY:END -->
