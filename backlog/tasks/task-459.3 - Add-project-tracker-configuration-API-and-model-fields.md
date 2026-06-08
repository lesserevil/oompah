---
id: TASK-459.3
title: Add project tracker configuration API and model fields
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/models.py
  - oompah/projects.py
  - oompah/server.py
  - tests/test_projects_crud.py
parent_task_id: TASK-459
priority: high
ordinal: 125000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add per-project tracker fields, central task-hub configuration, legacy_backlog_enabled, legacy_backlog_dispatch, and cutover timestamp support to Project, ProjectStore, create/update APIs, and validation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New projects can default to GitHub Issues while existing projects preserve current behavior.
- [ ] #2 Per-project tracker settings round-trip through projects.json and API responses.
<!-- AC:END -->
