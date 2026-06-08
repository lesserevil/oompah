---
id: TASK-461.1
title: Resolve trackers per project through the adapter registry
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.5
  - TASK-459.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_backlog_tracker.py
parent_task_id: TASK-461
priority: high
ordinal: 137000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update orchestrator tracker construction and caching so each project uses its configured tracker backend. Preserve legacy Backlog behavior while allowing GitHub-backed projects to share the central task hub.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Project tracker lookup can return BacklogMdTracker or GitHubIssueTracker.
- [ ] #2 Tracker cache invalidation remains project-scoped where needed.
<!-- AC:END -->
