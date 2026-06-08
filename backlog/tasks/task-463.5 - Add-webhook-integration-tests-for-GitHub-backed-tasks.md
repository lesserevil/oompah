---
id: TASK-463.5
title: Add webhook integration tests for GitHub-backed tasks
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-463.4
  - TASK-463.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests/test_webhooks.py
parent_task_id: TASK-463
priority: medium
ordinal: 156000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add tests for webhook parsing, signature validation, cache invalidation, orchestrator refresh requests, issue/comment/status updates, project-field changes, PR events, and legacy Backlog hook preservation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Webhook tests do not require live GitHub network access.
- [ ] #2 GitHub and Backlog webhook paths are both covered.
<!-- AC:END -->
