---
id: TASK-461.5
title: >-
  Integrate completion verifier, retry, reopen, and Needs Human flows with
  GitHub
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.4
  - TASK-458.4
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests
parent_task_id: TASK-461
priority: high
ordinal: 141000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update verifier rejection comments, reopen operations, pending retry cancellation, Needs Human marking, cost metadata, and question-answer flows to write through the tracker protocol and support GitHub-backed tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Verifier pass/fail flows update GitHub issue comments and status.
- [ ] #2 Retry and manual close races are covered for GitHub-backed tasks.
<!-- AC:END -->
