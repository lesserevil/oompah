---
id: TASK-462.6
title: Add PR and release reconciliation tests
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-462
priority: medium
ordinal: 150000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add regression coverage for branch-to-issue indexing, PR metadata writes, stale In Review recovery, CI-fix sibling tasks, merge conflicts, YOLO direct merge, merge queue enqueue, and release-pick outcomes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tests cover GitHub-backed and legacy Backlog-backed PR flows where behavior differs.
- [ ] #2 Release branch PRs are verified without relying on GitHub closing keywords.
<!-- AC:END -->
