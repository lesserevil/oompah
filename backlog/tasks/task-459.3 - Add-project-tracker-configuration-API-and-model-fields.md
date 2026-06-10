---
id: TASK-459.3
title: Add project tracker configuration API and model fields
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 04:49'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/models.py
  - oompah/projects.py
  - oompah/server.py
  - tests/test_projects_crud.py
parent_task_id: TASK-459
priority: high
ordinal: 125000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add per-project tracker fields, central task-hub configuration, legacy_backlog_enabled, legacy_backlog_dispatch, and cutover timestamp support to Project, ProjectStore, create/update APIs, and validation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New projects can default to GitHub Issues while existing projects preserve current behavior.
- [ ] #2 Per-project tracker settings round-trip through projects.json and API responses.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 04:40
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 04:41
---
Understanding: TASK-459.3 requires adding per-project tracker fields (tracker_kind, tracker_owner, tracker_repo, github_project_node_id, legacy_backlog_enabled, legacy_backlog_dispatch, tracker_cutover_at) to the Project model in oompah/models.py, updating ProjectStore.UPDATABLE_FIELDS and update()/create() in oompah/projects.py to handle these new fields with proper validation, updating the server API endpoints (api_create_project and api_update_project) in oompah/server.py to accept and validate these fields, and adding comprehensive tests in tests/test_projects_crud.py. The dependency TASK-457.1 is Done (TrackerProtocol + ADAPTER_REGISTRY already in place). Plan: (1) add fields to Project dataclass with to_dict/from_dict/to_safe_dict; (2) update ProjectStore UPDATABLE_FIELDS and update()/create(); (3) update server.py create/update endpoints; (4) add tests.
---

author: oompah
created: 2026-06-09 04:48
---
Discovery: Key files are oompah/models.py (Project dataclass), oompah/projects.py (ProjectStore with UPDATABLE_FIELDS, update(), create()), oompah/server.py (api_create_project and api_update_project endpoints), and tests/test_projects_crud.py. The Project model had no tracker fields; all existing tests were passing. The migration plan (plans/github-issues-tracker-migration.md) specifies exactly which fields are needed: tracker_kind, tracker_owner, tracker_repo, github_project_node_id, legacy_backlog_enabled, legacy_backlog_dispatch, and a cutover timestamp (tracker_cutover_at).
---

author: oompah
created: 2026-06-09 04:48
---
Implementation: (1) oompah/models.py - Added 7 fields to Project dataclass: tracker_kind, tracker_owner, tracker_repo, github_project_node_id (all str|None), legacy_backlog_enabled, legacy_backlog_dispatch (bool, default False), tracker_cutover_at (datetime|None). Updated to_dict() to emit tracker fields when set, always emit legacy flags. Updated from_dict() to parse and validate all new fields with safe fallbacks. (2) oompah/projects.py - Added 7 new field names to UPDATABLE_FIELDS frozenset. Added validation blocks in update(): string/null coercion for str fields, bool coercion for flags, ISO 8601 datetime parsing for tracker_cutover_at with clear error. Updated create() signature to accept tracker_kind, tracker_owner, tracker_repo, github_project_node_id, legacy_backlog_enabled, legacy_backlog_dispatch; passes them to Project() constructor. (3) oompah/server.py - Updated api_create_project to extract and forward all 6 new fields. Updated api_update_project to accept and pre-validate tracker fields before delegating to ProjectStore.update(). (4) tests/test_projects_crud.py - Updated test_updatable_fields_are_correct to include the 7 new fields. Added 3 new test classes (49 new tests): TestProjectTrackerFields (model unit tests), TestProjectStoreTrackerFieldUpdate (store tests), TestProjectAPITrackerFields (API integration tests).
---

author: oompah
created: 2026-06-09 04:48
---
Verification: All tests pass. python -m pytest tests/test_projects_crud.py tests/test_tracker_protocol.py tests/test_config.py tests/test_backlog_tracker.py: 252 passed. New tests cover: (1) Project model defaults, to_dict/from_dict round-trips for all 7 new tracker fields; (2) ProjectStore.update() validation for type errors, null coercion, ISO 8601 parsing of tracker_cutover_at, persistence across reload; (3) API endpoint PATCH/GET for all tracker fields including invalid type rejection (400) and null clearing. Acceptance criteria verified: (1) Existing projects with no tracker fields preserve prior behavior (from_dict defaults all new fields to None/False). (2) Per-project tracker settings round-trip through projects.json and API responses (tested explicitly with persistence-across-reload tests).
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added per-project tracker configuration fields (tracker_kind, tracker_owner, tracker_repo, github_project_node_id, legacy_backlog_enabled, legacy_backlog_dispatch, tracker_cutover_at) to Project model, ProjectStore UPDATABLE_FIELDS and update()/create(), and server API endpoints (create/update project). 49 new tests added to tests/test_projects_crud.py covering model round-trips, store validation, persistence, and API integration. All 252 relevant tests pass. Branch pushed to origin/epic-TASK-459.
<!-- SECTION:FINAL_SUMMARY:END -->
