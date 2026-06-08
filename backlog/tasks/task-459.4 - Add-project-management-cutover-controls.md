---
id: TASK-459.4
title: Add project management cutover controls
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/templates/projects.html
  - tests
parent_task_id: TASK-459
priority: medium
ordinal: 126000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update the projects management UI to show tracker backend, central task hub, legacy Backlog visibility/dispatch flags, and a guarded cutover action that warns existing Backlog tasks will not be migrated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Operators can see and edit tracker settings for each managed project.
- [ ] #2 Cutover copy explicitly states existing Backlog.md tasks are not migrated.
<!-- AC:END -->
