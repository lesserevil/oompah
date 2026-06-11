---
id: TASK-464
title: >-
  GitHub Issues migration phase 8: managed project cutover and Backlog
  decommission
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-11 17:34'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462
  - TASK-463
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 157000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cut managed projects over to GitHub Issues without migrating existing Backlog.md tasks. Provide dual-read/legacy-dispatch controls, ProjectStore tracker-aware sync, operator cutover flow, rollback path, and final Backlog decommission safeguards. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New tasks in all managed repos are GitHub Issues.
- [ ] #2 Existing Backlog.md tasks are not copied to GitHub.
- [ ] #3 GitHub-backed projects do not create new Backlog task files.
<!-- AC:END -->
