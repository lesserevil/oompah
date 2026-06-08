---
id: TASK-460.4
title: Add guards against new Backlog task files in GitHub-backed work
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
  - TASK-460.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_completion_verifier.py
parent_task_id: TASK-460
priority: high
ordinal: 134000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Detect and reject new backlog/tasks or backlog/completed files created during GitHub-backed task runs. Surface clear completion-verifier failures, dashboard alerts, and optional PR-check guidance instead of silently accepting a second task source.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed tasks fail verification if they add Backlog task files.
- [ ] #2 The guard does not block legacy Backlog task updates.
<!-- AC:END -->
