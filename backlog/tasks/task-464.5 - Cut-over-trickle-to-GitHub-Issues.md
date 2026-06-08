---
id: TASK-464.5
title: Cut over trickle to GitHub Issues
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.4
references:
  - plans/github-issues-tracker-migration.md
parent_task_id: TASK-464
priority: high
ordinal: 162000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the managed-project cutover workflow to trickle after the low-risk repo has run cleanly. Verify task creation, dispatch, PR links, review reconciliation, release-pick metadata, and no new Backlog task files after cutover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New trickle tasks are GitHub Issues in the central task hub.
- [ ] #2 trickle legacy Backlog tasks are visible/dispatchable only according to configured flags.
<!-- AC:END -->
