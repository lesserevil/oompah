---
id: TASK-459.1
title: Extend issue API schema for tracker identity
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.2
  - TASK-458.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - tests/test_server_issue_detail.py
  - tests/test_dashboard_draft_epics.py
parent_task_id: TASK-459
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update issue serialization and request validation to include tracker_kind, tracker_owner, tracker_repo, issue_number, display_identifier, GitHub URL, project_id, managed_repo, target_branch, work_branch, and legacy marker fields.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GET /api/v1/issues and detail responses expose tracker metadata.
- [ ] #2 Backlog-backed responses remain backward-compatible.
<!-- AC:END -->
