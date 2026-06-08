---
id: TASK-463.3
title: Update webhook forwarder event set and documentation
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-463.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - docs/webhook-forwarding.md
  - plans/backlog-task-change-webhooks.md
parent_task_id: TASK-463
priority: medium
ordinal: 154000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update local development and operator docs for gh webhook forward so issue, issue_comment, label, project item/field, pull_request, and push events reach oompah. Include verification and troubleshooting steps.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Docs list the required GitHub events for GitHub-backed tasks.
- [ ] #2 Docs distinguish GitHub task webhooks from legacy Backlog post-commit webhooks.
<!-- AC:END -->
