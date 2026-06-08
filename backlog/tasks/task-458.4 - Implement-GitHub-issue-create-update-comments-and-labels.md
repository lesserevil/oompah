---
id: TASK-458.4
title: 'Implement GitHub issue create, update, comments, and labels'
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 118000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement create_issue, update_issue, close_issue, reopen_issue, archive_issue, add_comment, fetch_comments, add_label, and remove_label for GitHub-backed tasks. Preserve oompah status semantics through the Oompah Status field instead of label-only state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Create returns a fully qualified GitHub issue identifier and URL.
- [ ] #2 Status, comments, and labels round-trip through mocked GitHub APIs.
<!-- AC:END -->
