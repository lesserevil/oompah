---
id: TASK-459.2
title: Make issue mutation endpoints backend-neutral
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.1
  - TASK-458.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - tests/test_server_issue_enhance.py
  - tests/test_server_label_api.py
parent_task_id: TASK-459
priority: high
ordinal: 124000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update create, patch, comment, label, and detail endpoints so they call only tracker protocol methods and support GitHub-backed identifiers. Handle URL-encoded identifiers and require project_id or managed_repo when creating new tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Create/update/comment/label endpoints work for GitHub and Backlog trackers in tests.
- [ ] #2 Route parsing cannot confuse slashes in fully qualified GitHub identifiers.
<!-- AC:END -->
