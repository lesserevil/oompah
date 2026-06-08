---
id: TASK-457.5
title: Audit and isolate direct BacklogMdTracker assumptions
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.3
  - TASK-457.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - oompah/error_watcher.py
parent_task_id: TASK-457
priority: high
ordinal: 113000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Find every direct BacklogMdTracker type check, constructor call, task-file path assumption, worker-workspace status read, and Backlog-specific comment in server/orchestrator/watchers. Convert generic call sites to the tracker protocol and document explicitly legacy-only paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Generic flows no longer assume tasks are files in a managed checkout.
- [ ] #2 Legacy Backlog-only paths are named and guarded.
<!-- AC:END -->
