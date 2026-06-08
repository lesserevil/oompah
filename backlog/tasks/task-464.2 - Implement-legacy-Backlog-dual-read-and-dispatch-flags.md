---
id: TASK-464.2
title: Implement legacy Backlog dual-read and dispatch flags
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.1
  - TASK-461.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests
parent_task_id: TASK-464
priority: high
ordinal: 159000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement legacy_backlog_enabled and legacy_backlog_dispatch semantics. Existing Backlog tasks may remain visible or dispatchable by explicit project setting, but all new tasks and follow-ups should use GitHub Issues after cutover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Legacy Backlog tasks can be visible without being dispatchable.
- [ ] #2 Follow-up tasks from legacy runs go to GitHub unless explicitly configured otherwise.
<!-- AC:END -->
