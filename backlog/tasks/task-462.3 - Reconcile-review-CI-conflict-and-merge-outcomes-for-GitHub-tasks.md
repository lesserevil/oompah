---
id: TASK-462.3
title: 'Reconcile review, CI, conflict, and merge outcomes for GitHub tasks'
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.2
  - TASK-461.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests/test_orchestrator_merged.py
parent_task_id: TASK-462
priority: high
ordinal: 147000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update review polling and webhook-driven reconciliation so open PRs mark tasks In Review, failed CI marks Needs CI Fix, conflicts mark Needs Rebase or Needs Human, merged PRs mark Merged, and closed-unmerged PRs reopen or escalate with comments.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Default-branch and release-branch PR outcomes are reconciled explicitly.
- [ ] #2 Closed-unmerged reviews never leave tasks indefinitely In Review.
<!-- AC:END -->
