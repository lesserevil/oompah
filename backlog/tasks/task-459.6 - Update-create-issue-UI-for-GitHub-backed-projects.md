---
id: TASK-459.6
title: Update create issue UI for GitHub-backed projects
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.2
  - TASK-459.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/templates/dashboard.html
  - tests/test_server_issue_enhance.py
parent_task_id: TASK-459
priority: high
ordinal: 128000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Revise the create issue modal so GitHub-backed projects create GitHub Issues through oompah, not Backlog.md files. Require a target managed project, expose target branch, issue type, priority, focus labels, and optional parent epic.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Creating a task for a GitHub-backed project never writes a Backlog task file.
- [ ] #2 The modal still supports legacy Backlog projects during transition.
<!-- AC:END -->
