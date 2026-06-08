---
id: TASK-462.5
title: Adapt release-pick metadata and child task creation to GitHub Issues
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.3
  - TASK-454
  - TASK-455
  - TASK-456
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - oompah/templates/dashboard.html
parent_task_id: TASK-462
priority: high
ordinal: 149000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Integrate the release-pick workstream with GitHub issue fields/body metadata. Source tasks should track backport targets, child GitHub tasks, target branches, cherry-pick status, PR links, conflicts, and merged outcomes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Release-pick children are GitHub Issues for GitHub-backed projects.
- [ ] #2 Conflict states preserve worktrees and surface actionable comments.
<!-- AC:END -->
