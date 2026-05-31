---
id: TASK-70
title: Add full CRUD to projects
status: Done
assignee: []
created_date: 2026-03-08 15:36
updated_date: 2026-03-08 15:42
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-xys
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-xys
  target_branch: null
  url: null
  created_at: '2026-03-08T15:36:38Z'
  updated_at: '2026-03-08T15:42:43Z'
  closed_at: '2026-03-08T15:42:43Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
We need to be able to modify project data after projects get added.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 84f0731c-778a-4958-aea5-ba6f8515661f
author: oompah
created: 2026-03-08T15:36:49Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 74d3b58b-0f48-4061-8715-9e0fb294ff81
author: oompah
created: 2026-03-08T15:36:50Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3db56315-096b-4b8e-aba9-4f8fa7e79c90
author: oompah
created: 2026-03-08T15:37:16Z

Agent stalled 1 time(s) (27s (83143 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e425432d-1b5d-4bcf-94b6-beae8a0e4427
author: oompah
created: 2026-03-08T15:37:26Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7fc28c7b-c065-46a4-935e-870d34b4edb1
author: oompah
created: 2026-03-08T15:37:27Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 83e792aa-f5c9-4c6a-9845-4530db8ca15c
author: Shawn Edwards
created: 2026-03-08T15:38:01Z

I understand the issue: We need full CRUD (Create, Read, Update, Delete) for projects. Looking at the codebase, I can see that: 1) ProjectStore already has create(), get(), list_all(), update(), and delete() methods. 2) The server already has GET /api/v1/projects (list), POST /api/v1/projects (create), PATCH /api/v1/projects/{id} (update), DELETE /api/v1/projects/{id} (delete). 3) However, there's no GET /api/v1/projects/{id} (read single project) endpoint. Let me also check what fields/validation the update endpoint handles and whether the project store update() properly validates fields.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7a144645-6f63-4988-9f31-9aadf62a107f
author: Shawn Edwards
created: 2026-03-08T15:38:23Z

Discovery: The existing codebase already has most CRUD operations in place. Here's what exists vs. what's missing:

SERVER ENDPOINTS:
- GET /api/v1/projects (list) ✅
- POST /api/v1/projects (create) ✅
- PATCH /api/v1/projects/{id} (update) ✅ - but limited field support
- DELETE /api/v1/projects/{id} (delete) ✅
- GET /api/v1/projects/{id} (read single) ❌ MISSING

PROJECTSTORE:
- list_all() ✅
- get() ✅
- create() ✅
- update() ✅ - but no validation on allowed fields
- delete() ✅

UI (projects.html):
- List projects ✅
- Add project form ✅
- Toggle YOLO ✅
- Delete ✅
- Edit project fields ❌ MISSING

Plan:
1. Add GET /api/v1/projects/{project_id} endpoint for reading a single project
2. Improve PATCH endpoint with proper validation (reject unknown fields, validate non-empty name)
3. Add edit UI to projects.html so users can modify project data (name, branch, git user, etc.)
4. Add comprehensive tests for all project CRUD operations
5. Ensure ProjectStore.update() validates fields properly
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 07486720-1d5c-4ca2-8602-a67edf077343
author: Shawn Edwards
created: 2026-03-08T15:41:56Z

Implementation complete. Changes made:

1. **oompah/projects.py** - Enhanced ProjectStore.update():
   - Added UPDATABLE_FIELDS constant (name, repo_url, branch, git_user_name, git_user_email, yolo, log_path)
   - Added validation: rejects unknown/immutable fields (raises ProjectError)
   - Added validation: rejects empty name
   - Trims whitespace from name
   - Added docstring

2. **oompah/server.py** - API endpoints:
   - Added GET /api/v1/projects/{project_id} for reading a single project
   - Improved PATCH /api/v1/projects/{project_id}: catches ProjectError for 400 responses, added repo_url as updatable, removed repo_path (immutable)

3. **oompah/templates/projects.html** - UI:
   - Added Edit button to each project card
   - Added inline edit form with all mutable fields (name, repo_url, branch, git user name/email, log path)
   - Added client-side validation (required name)
   - Added error display for failed saves
   - Added log_path display in project cards

4. **tests/test_projects_crud.py** - 44 tests covering:
   - ProjectStore.update() for each field, multiple fields, persistence, validation
   - ProjectStore.get() for existing and non-existent projects
   - ProjectStore.delete() with persistence verification
   - ProjectStore.list_all()
   - All API endpoints via FastAPI TestClient (GET single, PATCH, DELETE, validation errors)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e1ee9307-163c-422f-8e8c-b6741d39f6ca
author: Shawn Edwards
created: 2026-03-08T15:42:01Z

Verification: All 320 tests pass (276 existing + 44 new). No regressions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 74beee91-cd4b-4d3e-aaae-3e3c6f035b06
author: Shawn Edwards
created: 2026-03-08T15:42:38Z

PR created: https://github.com/lesserevil/oompah/pull/18
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1c3a7bd6-463a-47b2-8f9f-715d72718f90
author: oompah
created: 2026-03-08T15:42:44Z

Agent completed successfully in 318s (1447046 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
