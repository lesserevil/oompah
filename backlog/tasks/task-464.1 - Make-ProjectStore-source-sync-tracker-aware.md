---
id: TASK-464.1
title: Make ProjectStore source sync tracker-aware
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
  - TASK-463.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/projects.py
  - tests/test_projects.py
parent_task_id: TASK-464
priority: high
ordinal: 158000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
For GitHub-backed projects, keep git self-heal and default-branch fast-forwarding, but skip Backlog compatibility checks, Backlog conflict repair/quarantine, and Backlog hook setup. Preserve current behavior for legacy Backlog projects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 sync_project_sources reports GitHub tracker status for GitHub-backed projects.
- [ ] #2 Backlog conflict repair remains active only for legacy Backlog projects.
<!-- AC:END -->
