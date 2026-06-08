---
id: TASK-461.3
title: Persist target and work branch metadata before worktree creation
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.2
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/projects.py
  - tests/test_projects.py
parent_task_id: TASK-461
priority: high
ordinal: 139000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Generate GitHub-safe work branch names, validate Target Branch against project branch patterns, persist Work Branch and Target Branch metadata to the issue, and create worktrees from the intended base branch.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Branch names never rely on bare task numbers.
- [ ] #2 Review reconciliation can find the task from Work Branch metadata.
<!-- AC:END -->
