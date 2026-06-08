---
id: TASK-460.1
title: Build oompah task command wrapper
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - pyproject.toml
  - oompah/server.py
  - tests
parent_task_id: TASK-460
priority: high
ordinal: 131000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add an oompah task CLI or equivalent server-backed command surface for view, comment, create, child-create, set-status, add-label, remove-label, and set-dependency. The wrapper should call the local oompah API and work for both GitHub and legacy Backlog trackers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Agents have one tracker-neutral command surface for task operations.
- [ ] #2 Wrapper commands fail loudly with actionable errors when the local server is unavailable.
<!-- AC:END -->
