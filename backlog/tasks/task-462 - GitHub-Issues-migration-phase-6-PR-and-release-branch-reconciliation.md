---
id: TASK-462
title: 'GitHub Issues migration phase 6: PR and release branch reconciliation'
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 144000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update PR creation, stale review reconciliation, CI repair, merge conflict handling, YOLO/merge queue handling, and release-pick automation so review outcomes update central GitHub task state explicitly. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 PR lifecycle updates GitHub-backed tasks through review, CI, conflict, merged, and archived states.
- [ ] #2 Release branch PRs do not rely on GitHub auto-close semantics.
- [ ] #3 Branch-to-task resolution uses Work Branch metadata, not task-number guessing.
<!-- AC:END -->
