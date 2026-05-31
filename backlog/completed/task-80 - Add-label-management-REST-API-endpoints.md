---
id: TASK-80
title: Add label management REST API endpoints
status: Done
assignee: []
created_date: 2026-03-08 18:04
updated_date: 2026-03-08 19:05
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-5e0
  state: closed
  parent_id: oompah-7rw
  dependencies: []
  branch_name: oompah-5e0
  target_branch: null
  url: null
  created_at: '2026-03-08T18:04:12Z'
  updated_at: '2026-03-08T19:05:25Z'
  closed_at: '2026-03-08T19:05:25Z'
parent: TASK-76
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add POST /api/v1/issues/{identifier}/labels and DELETE /api/v1/issues/{identifier}/labels/{label} endpoints to server.py. These will use the existing tracker.add_label() and tracker.remove_label() methods. These endpoints are needed by the draft badge toggle (oompah-6cd) and auto-draft on epic creation (oompah-sei). Include request body with {label, project_id}. Add tests in tests/test_server_label_api.py covering: (1) successful add label, (2) successful remove label, (3) broadcast_issues called after label change, (4) cache invalidation. Follow the pattern of existing API endpoints in server.py.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 0058e9b0-5ae0-480e-8651-bf3e9ab06473
author: oompah
created: 2026-03-08T19:02:26Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2a4362f9-24ed-4348-8b8b-863d91521bea
author: oompah
created: 2026-03-08T19:02:27Z

Focus: Epic Planner
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0c6744c3-50ed-4910-b454-64797c42e695
author: Shawn Edwards
created: 2026-03-08T19:03:04Z

I understand the issue: This is a task (not an epic) to add POST /api/v1/issues/{identifier}/labels and DELETE /api/v1/issues/{identifier}/labels/{label} endpoints to oompah/server.py. The tracker already has add_label() and remove_label() methods. Tests should go in tests/test_server_label_api.py covering: successful add, successful remove, broadcast_issues called, and cache invalidation. The task is self-contained and implementation-ready.

Since this is already a well-scoped, single-session task (not an epic that needs decomposition), I will implement it directly rather than decompose it into subtasks. My plan: (1) Add the two endpoints to server.py following the existing API pattern, (2) Write tests in tests/test_server_label_api.py, (3) Run tests to verify, (4) Commit and push.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3e6dc164-ae56-4d97-ba8d-578523dfe4de
author: Shawn Edwards
created: 2026-03-08T19:03:11Z

Found the relevant code: oompah/server.py has the FastAPI app with existing API patterns (api_update_issue, api_add_comment, etc.). The tracker's add_label() and remove_label() methods are in oompah/tracker.py. The _api_cache.invalidate() pattern and broadcast_issues() call pattern are clear from existing endpoints. I'll follow the pattern from api_update_issue and api_add_comment to implement the label endpoints.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c7a0d925-8caa-49e0-b7e8-2f641599d104
author: Shawn Edwards
created: 2026-03-08T19:04:49Z

Implementation complete. Added to oompah/server.py:
- POST /api/v1/issues/{identifier}/labels — reads {label, project_id} from body, calls tracker.add_label(), invalidates cache, broadcasts issues, returns 201
- DELETE /api/v1/issues/{identifier}/labels/{label} — reads project_id from query param, calls tracker.remove_label(), invalidates cache, broadcasts issues, returns 200

Both follow the existing API pattern (try/except, JSONResponse, _api_cache.invalidate, broadcast_issues). Added tests/test_server_label_api.py with 13 tests covering all 4 required scenarios.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1e5197a2-f8b4-48ff-813d-5d83f4fd36fb
author: Shawn Edwards
created: 2026-03-08T19:04:52Z

Verification: all 408 tests pass (uv run pytest). New label API tests: 13/13 pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: acc65038-4d01-4ebc-ad46-a8ae1ab993f7
author: Shawn Edwards
created: 2026-03-08T19:05:21Z

Completed. PR: https://github.com/lesserevil/oompah/pull/23

Delivered:
- POST /api/v1/issues/{identifier}/labels endpoint in server.py
- DELETE /api/v1/issues/{identifier}/labels/{label} endpoint in server.py
- 13 tests in tests/test_server_label_api.py (all passing)
- All 408 tests pass
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4e245697-eb1a-4d36-95cf-5bc15045a082
author: oompah
created: 2026-03-08T19:05:25Z

Agent completed successfully in 179s (955162 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
