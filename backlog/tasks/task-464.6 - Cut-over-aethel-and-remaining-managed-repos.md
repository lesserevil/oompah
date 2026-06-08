---
id: TASK-464.6
title: Cut over aethel and remaining managed repos
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.5
references:
  - plans/github-issues-tracker-migration.md
parent_task_id: TASK-464
priority: high
ordinal: 163000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the cutover workflow to aethel and the rest of the managed repositories. Verify each repo has GitHub task creation, dispatch, PR reconciliation, webhook refresh, and Backlog file creation guardrails enabled.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every managed repo creates new work as GitHub Issues.
- [ ] #2 No managed repo depends on Backlog.md for new task creation.
<!-- AC:END -->
