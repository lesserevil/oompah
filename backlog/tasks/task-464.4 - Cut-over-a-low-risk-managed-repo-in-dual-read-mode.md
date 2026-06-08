---
id: TASK-464.4
title: Cut over a low-risk managed repo in dual-read mode
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.3
  - TASK-462.6
  - TASK-463.5
references:
  - plans/github-issues-tracker-migration.md
parent_task_id: TASK-464
priority: high
ordinal: 161000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Perform the first production cutover on a low-risk managed repository. Create a GitHub-backed test task, dispatch it, open or simulate review flow, verify status/comments/links, and leave legacy Backlog tasks visible but not migrated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A real managed repo creates and completes a GitHub-backed smoke task.
- [ ] #2 Existing Backlog.md tasks in that repo are not migrated.
<!-- AC:END -->
