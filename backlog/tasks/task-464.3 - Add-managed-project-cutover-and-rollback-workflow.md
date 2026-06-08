---
id: TASK-464.3
title: Add managed-project cutover and rollback workflow
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.2
  - TASK-459.4
  - TASK-461.7
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - oompah/templates/projects.html
  - docs
parent_task_id: TASK-464
priority: high
ordinal: 160000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement operator workflow for pausing a project, waiting for or cancelling agents, recording cutover timestamp, enabling GitHub tracker settings, verifying test task creation/dispatch/PR flow, unpausing, and rolling back if needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Cutover flow is documented and exposed through project management UI or API.
- [ ] #2 Rollback restores legacy Backlog dispatch settings without deleting GitHub issues.
<!-- AC:END -->
