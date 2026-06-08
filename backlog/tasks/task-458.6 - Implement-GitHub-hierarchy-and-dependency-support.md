---
id: TASK-458.6
title: Implement GitHub hierarchy and dependency support
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 120000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Support epics, child tasks, and blockers using GitHub sub-issues and issue dependencies where available. Add adapter-level fallback metadata for any GitHub API surface that is unavailable, while preserving the tracker protocol.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 fetch_children and add_dependency work through the protocol.
- [ ] #2 Fallback relationship metadata renders the same normalized Issue relationships.
<!-- AC:END -->
