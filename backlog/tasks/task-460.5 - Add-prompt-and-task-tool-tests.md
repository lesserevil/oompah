---
id: TASK-460.5
title: Add prompt and task-tool tests
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-460
priority: medium
ordinal: 135000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add snapshot and behavioral coverage for GitHub-backed prompts, legacy Backlog prompts, oompah task wrapper operations, local-server failures, and task creation routing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Prompt tests prove Backlog commands are absent for GitHub-backed tasks.
- [ ] #2 Task wrapper tests cover create, comment, status, labels, and errors.
<!-- AC:END -->
