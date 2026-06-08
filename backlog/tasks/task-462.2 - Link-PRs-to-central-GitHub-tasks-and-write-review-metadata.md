---
id: TASK-462.2
title: Link PRs to central GitHub tasks and write review metadata
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/scm.py
  - tests
parent_task_id: TASK-462
priority: high
ordinal: 146000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update PR body generation and review handoff so PRs reference the central GitHub issue, store Review URL and Review Number metadata, and avoid relying on closing keywords except where explicitly safe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Opened PRs include a stable link to the central task hub issue.
- [ ] #2 Task metadata records source branch, target branch, PR number, and PR URL.
<!-- AC:END -->
