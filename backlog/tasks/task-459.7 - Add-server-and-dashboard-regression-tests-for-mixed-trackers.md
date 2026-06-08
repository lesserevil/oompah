---
id: TASK-459.7
title: Add server and dashboard regression tests for mixed trackers
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.6
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-459
priority: medium
ordinal: 129000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cover mixed Backlog/GitHub issue lists, project filtering, detail panels, comments, labels, create flows, status updates, cache invalidation, and tracker identity display using mocked trackers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Mixed tracker board data cannot collide on bare task numbers.
- [ ] #2 All updated endpoints have GitHub-backed and Backlog-backed test cases.
<!-- AC:END -->
