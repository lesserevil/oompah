---
id: TASK-464.7
title: 'Decommission default Backlog prompts, hooks, and reports'
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.6
  - TASK-460.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - WORKFLOW.md
  - oompah/orchestrator.py
  - oompah/server.py
parent_task_id: TASK-464
priority: medium
ordinal: 164000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After managed projects are cut over, remove Backlog.md from default prompts and default project lifecycle, keep BacklogMdTracker behind explicit legacy flags, add reports for new Backlog files since cutover, and resolve or supersede the old Backlog-only workstream TASK-402.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Default oompah workflow no longer presents Backlog.md as the active tracker.
- [ ] #2 Operators can report any post-cutover Backlog task files.
- [ ] #3 TASK-402 is explicitly closed, archived, or documented as superseded.
<!-- AC:END -->
