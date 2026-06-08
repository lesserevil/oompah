---
id: TASK-463.1
title: Expand GitHub webhook event parsing for issues and project fields
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.4
  - TASK-459.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - tests/test_webhooks.py
parent_task_id: TASK-463
priority: high
ordinal: 152000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add parsing and validation for issues, issue_comment, label, pull_request, push, and project-field events needed by GitHub-backed task tracking. Reuse existing GitHub webhook auth and redaction patterns.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Issue, comment, label, PR, push, and project field events are parsed into normalized events.
- [ ] #2 Invalid signatures and unsupported events are handled safely.
<!-- AC:END -->
