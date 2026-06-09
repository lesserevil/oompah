---
id: TASK-459.1
title: Extend issue API schema for tracker identity
status: Done
assignee:
  - oompah
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 22:34'
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

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 22:15
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 22:15
---
Understanding: This task requires extending the issue API schema to include tracker identity fields: tracker_kind, tracker_owner, tracker_repo, issue_number, display_identifier, GitHub URL, project_id, managed_repo, target_branch, work_branch, and legacy marker fields. I need to update issue serialization in server.py and request validation. Starting codebase exploration.
---

author: oompah
created: 2026-06-09 22:18
---
Discovery: Found the key files. Issue model (oompah/models.py) already has tracker_kind, owner, repo, issue_number, display_identifier, provider_url fields (added by TASK-457.2), but field names 'owner'/'repo' need to be standardized to 'tracker_owner'/'tracker_repo'. Missing: managed_repo, work_branch, is_legacy. Server serialization in _fetch_and_serialize_issues and api_issue_full_detail needs all tracker identity fields. _issue_display_fields should prefer model's display_identifier when set (GitHub issues). api_create_issue needs to accept managed_repo, work_branch, target_branch in request body.
---

author: oompah
created: 2026-06-09 22:33
---
Implementation: Updated oompah/models.py Issue dataclass - renamed owner/repo to tracker_owner/tracker_repo, added managed_repo, work_branch, is_legacy fields. Updated server.py: _issue_display_fields now prefers model display_identifier (GitHub short form), _fetch_and_serialize_issues and api_issue_full_detail now include all tracker identity fields (tracker_kind, tracker_owner, tracker_repo, issue_number, url, managed_repo, target_branch, work_branch, is_legacy). api_create_issue accepts and validates managed_repo/target_branch/work_branch in request body, validates managed_repo format (owner/repo). api_update_issue accepts same tracker fields and passes them to tracker adapter. Added 25 tests in tests/test_server_tracker_identity_schema.py.
---

author: oompah
created: 2026-06-09 22:34
---
Verification: All 25 new tests pass. Also confirmed 389 tests across the broader test suite pass (server, models, backlog tracker, tracker protocol, dashboard, project CRUD). No regressions. Tests cover: board entry serialization with tracker fields for Backlog/GitHub/legacy issues, detail endpoint with all tracker fields, display_identifier preference (model vs computed fallback), url vs provider_url fallback, create endpoint validation (managed_repo format, field passthrough), update endpoint validation and field forwarding, and Issue model dataclass defaults.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Extended issue API schema for tracker identity: renamed Issue.owner/repo to tracker_owner/tracker_repo, added managed_repo/work_branch/is_legacy to Issue model. Updated server serialization (_fetch_and_serialize_issues, api_issue_full_detail) to expose all tracker identity fields. Updated api_create_issue and api_update_issue to accept/validate managed_repo (owner/repo format), target_branch, work_branch. display_identifier now prefers model field over computed fallback enabling GitHub short forms. Backlog-backed issues remain backward-compatible (null tracker fields, is_legacy=false). 25 new tests in tests/test_server_tracker_identity_schema.py, all passing.
<!-- SECTION:FINAL_SUMMARY:END -->
