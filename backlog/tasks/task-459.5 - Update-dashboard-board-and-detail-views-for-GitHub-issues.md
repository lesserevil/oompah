---
id: TASK-459.5
title: Update dashboard board and detail views for GitHub issues
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.1
  - TASK-459.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/templates/dashboard.html
  - tests/test_dashboard_draft_epics.py
parent_task_id: TASK-459
priority: high
ordinal: 127000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Show GitHub-backed issue display identifiers, GitHub issue links, tracker kind, project name, sub-issues, blockers, comments, review links, and a legacy marker for Backlog-backed tasks. Keep board grouping based on canonical oompah status.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub issue cards link to the GitHub issue URL.
- [ ] #2 Legacy Backlog task cards remain usable and visually distinct.
<!-- AC:END -->
