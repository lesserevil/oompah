---
id: TASK-463.4
title: Disable Backlog post-commit hooks for GitHub-backed projects
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/backlog_webhooks.py
  - oompah/server.py
  - oompah/__main__.py
parent_task_id: TASK-463
priority: high
ordinal: 155000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make startup, project create, and project update hook installation tracker-aware. GitHub-backed projects should skip Backlog hook installation and ignore Backlog webhook receipts for that project.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed projects do not install or depend on Backlog post-commit hooks.
- [ ] #2 Legacy Backlog projects continue to install hooks idempotently.
<!-- AC:END -->
