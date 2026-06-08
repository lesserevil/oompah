---
id: TASK-455.5
title: Handle cherry-pick conflicts without losing work
status: Backlog
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:31'
labels:
  - task
dependencies:
  - TASK-455.4
parent_task_id: TASK-455
priority: high
ordinal: 100000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When a cherry-pick conflicts, leave the worktree intact, mark the child task Needs Rebase or Needs Human with a diagnostic comment, update source metadata to conflict, and ensure later ticks do not overwrite the conflicted workspace.
<!-- SECTION:DESCRIPTION:END -->
