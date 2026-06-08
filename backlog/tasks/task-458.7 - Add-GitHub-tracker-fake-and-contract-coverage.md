---
id: TASK-458.7
title: Add GitHub tracker fake and contract coverage
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.6
  - TASK-457.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 121000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build fake GitHub fixtures or mocked REST/GraphQL responses that run the shared tracker contract suite and cover auth failures, rate limits, pagination, issue fields, body fallback, labels, comments, and relationship operations.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHubIssueTracker passes all shared tracker contract tests.
- [ ] #2 Failure cases are tested without making live network calls.
<!-- AC:END -->
