---
id: TASK-84
title: Write tests for draft epic kanban visibility
status: Done
assignee: []
created_date: 2026-03-08 18:04
updated_date: 2026-03-08 19:21
labels:
- archive:yes
- merged
- beads-migrated
dependencies:
- TASK-81
- TASK-80
- TASK-82
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-bnm
  state: closed
  parent_id: oompah-7rw
  dependencies:
  - oompah-14u
  - oompah-5e0
  - oompah-7mb
  branch_name: oompah-bnm
  target_branch: null
  url: null
  created_at: '2026-03-08T18:04:51Z'
  updated_at: '2026-03-08T19:21:04Z'
  closed_at: '2026-03-08T19:21:04Z'
parent: TASK-76
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Write comprehensive tests for the draft epic kanban feature. Tests should go in tests/test_draft_epic_kanban.py. Coverage required: (1) Server-side: test that api_issues() in server.py includes draft epics in the column data (they have issue_type='epic' and labels=['draft']). Test that non-draft epics are still included in the response (they appear as swimlane headers on the frontend, but the API returns all issues). (2) Test that the issue entry for a draft epic includes the labels field with 'draft'. (3) Test the label API endpoints (POST /api/v1/issues/{id}/labels and DELETE /api/v1/issues/{id}/labels/{label}) once task oompah-5e0 is done. (4) Test tracker.add_label() and tracker.remove_label() calls. Use unittest.mock to mock tracker calls — follow the pattern in tests/test_tracker.py and tests/test_server_edit_protection.py. Run: make test to verify all pass.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: dcb15eca-dc8d-4147-a562-604d4b5b4742
author: oompah
created: 2026-03-08T19:15:26Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10259c64-8e7a-46eb-acf8-87ee3d4e3021
author: oompah
created: 2026-03-08T19:15:27Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7627fa0c-c9b0-42e8-b078-725b54b5f82d
author: oompah
created: 2026-03-08T19:15:54Z

Agent stalled 1 time(s) (28s (73685 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 01601336-930c-43c8-891c-80b6c890a77e
author: oompah
created: 2026-03-08T19:16:05Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d5feea7e-9664-4c00-82c8-472082df57c7
author: oompah
created: 2026-03-08T19:16:05Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ca3af9ac-08cb-4eac-aee2-70e2ed2c7daa
author: Shawn Edwards
created: 2026-03-08T19:16:41Z

I understand the issue: Write comprehensive tests in tests/test_draft_epic_kanban.py covering (1) server-side api_issues() includes draft epics in column data, (2) non-draft epics are also included, (3) draft epic entries include labels with 'draft', (4) label API endpoints (POST/DELETE), (5) tracker.add_label() and tracker.remove_label() calls. There's already test_dashboard_draft_epics.py and test_server_label_api.py with overlapping coverage. I'll write focused, non-overlapping tests that cover the specific behavior described in the issue, following the mocking patterns in test_tracker.py and test_server_edit_protection.py.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6179c3f4-6320-42f6-b4b4-e87c21d0c04c
author: Shawn Edwards
created: 2026-03-08T19:17:14Z

Discovery: Found all key code. api_issues() in server.py (line 316) builds issue entries with labels and issue_type fields, includes all epics (draft and non-draft). tracker.add_label() calls _run_bd(['label', 'add', identifier, label]), tracker.remove_label() wraps in try/except TrackerError. Label API endpoints at lines 539 and 566. Existing tests in test_dashboard_draft_epics.py and test_server_label_api.py overlap significantly but this issue asks for a consolidated test_draft_epic_kanban.py. Writing tests now.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fe5f2634-57bc-4d6a-a2a9-31957e76a6d7
author: Shawn Edwards
created: 2026-03-08T19:20:09Z

Implementation: Created tests/test_draft_epic_kanban.py with 45 tests across 8 test classes:
1. TestApiIssuesDraftEpicInColumns (7 tests) - draft epics appear in correct state columns
2. TestApiIssuesNonDraftEpicIncluded (4 tests) - non-draft epics still in response for swimlane headers
3. TestDraftEpicLabelsField (6 tests) - labels field serialization with 'draft' label
4. TestLabelApiAddEndpoint (8 tests) - POST label endpoint: success, validation, cache, broadcast, errors
5. TestLabelApiRemoveEndpoint (7 tests) - DELETE label endpoint: success, cache, broadcast, errors
6. TestTrackerAddLabel (3 tests) - tracker.add_label() calls _run_bd correctly
7. TestTrackerRemoveLabel (4 tests) - tracker.remove_label() with error swallowing behavior
8. TestDraftEpicEdgeCases (6 tests) - archived draft epics, sorting, children_counts, mixed types
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 62eed6fa-2600-4f7b-9a7f-d4f2bce012f8
author: Shawn Edwards
created: 2026-03-08T19:20:15Z

Verification: All 45 new tests pass. Full test suite: 585 passed, 9 warnings (pre-existing). No failures.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 115b07c2-02d3-44f5-abad-78295fd2abe5
author: Shawn Edwards
created: 2026-03-08T19:20:59Z

Completion: Delivered 45 tests in tests/test_draft_epic_kanban.py covering all 5 areas from the issue description: (1) api_issues() draft epic column data, (2) non-draft epic inclusion, (3) labels field serialization, (4) label API endpoints, (5) tracker add/remove label calls. All 585 tests pass. PR: https://github.com/lesserevil/oompah/pull/31
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 840f1e86-d369-4350-af95-f40cd94ffd93
author: oompah
created: 2026-03-08T19:21:05Z

Agent completed successfully in 301s (1345676 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
