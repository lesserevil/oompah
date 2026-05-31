---
id: TASK-79
title: Auto-add draft label to new epics from UI
status: Done
assignee: []
created_date: 2026-03-08 18:02
updated_date: 2026-03-08 19:10
labels:
- archive:yes
- merged
- beads-migrated
dependencies:
- TASK-80
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-sei
  state: closed
  parent_id: oompah-7rw
  dependencies:
  - oompah-5e0
  branch_name: oompah-sei
  target_branch: null
  url: null
  created_at: '2026-03-08T18:02:57Z'
  updated_at: '2026-03-08T19:10:15Z'
  closed_at: '2026-03-08T19:10:15Z'
parent: TASK-76
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When the dashboard create dialog creates an epic (type=epic), automatically add the 'draft' label to it. This ensures new epics from the UI always start as drafts and appear in the kanban. Can be done client-side (POST to label endpoint after creation) or server-side (in the create_issue API handler when type is epic).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 3ce32d48-41c8-4275-9d66-4b8819fceed8
author: oompah
created: 2026-03-08T19:07:18Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c1ceeb8c-6a4d-4668-ba56-852e9cc03789
author: oompah
created: 2026-03-08T19:07:18Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6f5e2b80-97df-490f-9c21-27cb7834a864
author: Shawn Edwards
created: 2026-03-08T19:07:43Z

I understand the issue: When a user creates an epic from the dashboard UI (POST /api/v1/issues with type=epic), the 'draft' label should be automatically added to it. This ensures new epics start as drafts and appear in the kanban. I'll implement this server-side in the api_create_issue handler (in oompah/server.py) by calling tracker.add_label after creating the issue when the type is 'epic'. This approach is cleaner than client-side as it's atomic and consistent. I'll also add corresponding tests in the test_server_label_api.py file.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 534ebc22-0e06-4ff0-babd-8662b4b65b1b
author: Shawn Edwards
created: 2026-03-08T19:07:58Z

Found the key code: The api_create_issue handler in oompah/server.py (around line 320) handles POST /api/v1/issues. After calling tracker.create_issue(), I need to add tracker.add_label(issue.identifier, 'draft') when the issue type is 'epic'. The tracker.add_label method already exists and is used elsewhere. This is the minimal server-side change needed.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2d17ecfa-85a6-4353-b159-a19f8fede3c3
author: Shawn Edwards
created: 2026-03-08T19:09:29Z

Implementation complete. Changed oompah/server.py in api_create_issue: extracted issue_type from request body before calling tracker.create_issue(), then added 3 lines to call tracker.add_label(issue.identifier, 'draft') when issue_type == 'epic'. Added tests/test_server_create_issue.py with 11 tests covering: epic gets draft label, non-epic types (task/bug/feature/default) don't get label, label added before broadcast, add_label failure propagates as 500, missing title still returns 400, broadcast called, cache invalidated, correct identifier used for label call.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d315d4a2-78ab-4f48-b6b2-49ad6a6f5829
author: Shawn Edwards
created: 2026-03-08T19:09:43Z

Verification: All 463 tests pass (uv run --extra dev pytest tests/ -v). 11 new tests for this feature all pass. No existing tests broken.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 50e04fba-47c1-47a2-8375-6ed1c4b46928
author: Shawn Edwards
created: 2026-03-08T19:10:11Z

PR created: https://github.com/lesserevil/oompah/pull/26

Summary: Added 3 lines to oompah/server.py api_create_issue handler to automatically add 'draft' label when creating epics. Added 11 tests in tests/test_server_create_issue.py. All 463 tests pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 055bbe22-359a-4720-8067-523aaa998a18
author: oompah
created: 2026-03-08T19:10:17Z

Agent completed successfully in 179s (1039820 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
