---
id: TASK-462.1
title: Build branch-to-issue index from tracker metadata
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_merge_queue.py
parent_task_id: TASK-462
priority: high
ordinal: 145000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace source-branch-to-task lookup that assumes branch names equal Backlog identifiers. Build a per-project index from GitHub Work Branch metadata and open/in-review issues, with legacy fallback for Backlog branches.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CI-fix and merge-conflict flows can resolve GitHub-backed tasks from PR source branches.
- [ ] #2 Legacy Backlog branch lookup continues to work.
<!-- AC:END -->
