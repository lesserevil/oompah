---
id: TASK-457.3
title: Make BacklogMdTracker implement the tracker protocol
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/tracker.py
  - tests/test_backlog_tracker.py
parent_task_id: TASK-457
priority: high
ordinal: 111000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Refactor the existing Backlog adapter only as needed to satisfy the new protocol. Preserve all existing Backlog.md CLI behavior, direct-file fallbacks, metadata handling, status canonicalization, and cache invalidation semantics.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Existing Backlog.md tests pass without intentional behavior changes.
- [ ] #2 Backlog-specific helper methods are isolated from protocol consumers.
<!-- AC:END -->
