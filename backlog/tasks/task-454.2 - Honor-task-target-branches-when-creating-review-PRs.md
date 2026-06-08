---
id: TASK-454.2
title: Honor task target branches when creating review PRs
status: Backlog
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:30'
labels:
  - task
dependencies:
  - TASK-454.1
parent_task_id: TASK-454
priority: high
ordinal: 92000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update review handoff so normal per-task PRs target Issue.target_branch when present, falling back to the project default branch. Preserve epic stacked/shared behavior and add tests proving release tasks open PRs into release branches.
<!-- SECTION:DESCRIPTION:END -->
