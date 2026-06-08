---
id: TASK-461.7
title: Add orchestrator lifecycle tests for GitHub-backed tasks
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.6
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-461
priority: medium
ordinal: 143000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add focused tests for candidate fetch, dispatch, claim, worker exit, retry, close, reopen, verifier rejection, Needs Human, watcher-created tasks, and mixed Backlog/GitHub projects using mocked trackers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed lifecycle tests do not require live GitHub network access.
- [ ] #2 Mixed tracker projects dispatch without cross-project task ID collisions.
<!-- AC:END -->
