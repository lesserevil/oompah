---
id: TASK-462.4
title: Update YOLO and merge queue paths for GitHub-backed tasks
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests/test_merge_queue.py
parent_task_id: TASK-462
priority: high
ordinal: 148000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make YOLO auto-merge, merge queue enqueue, queue-state display, and related notifications update GitHub-backed task state and comments through tracker protocol methods.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Merge queue success and failure paths update GitHub issue status and comments.
- [ ] #2 Queue-mode behavior remains unchanged for legacy Backlog tasks.
<!-- AC:END -->
