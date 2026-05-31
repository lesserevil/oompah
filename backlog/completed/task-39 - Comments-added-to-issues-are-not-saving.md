---
id: TASK-39
title: Comments added to issues are not saving
status: Done
assignee: []
created_date: 2026-03-07 05:18
updated_date: 2026-03-07 05:39
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: bug
beads:
  id: umpah-bz4
  state: closed
  parent_id: null
  dependencies: []
  branch_name: umpah-bz4
  target_branch: null
  url: null
  created_at: '2026-03-07T05:18:07Z'
  updated_at: '2026-03-07T05:39:23Z'
  closed_at: '2026-03-07T05:39:23Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When I use the web ui to add a comment to an issue, I can type in the comment and press 'post comment', but I cannot see the comment in the issue. The comment should be added to the issue.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: c8910931-f804-45db-9188-bb1fcdca36eb
author: oompah
created: 2026-03-07T05:19:18Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 28220116-743e-4f0d-bed9-f2198658f28b
author: oompah
created: 2026-03-07T05:19:20Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 78fcf999-035f-487f-93c8-25c232a830fd
author: oompah
created: 2026-03-07T05:19:54Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1c7ce76e-1910-4082-91d8-50a4aee09923
author: oompah
created: 2026-03-07T05:19:55Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6471e8ab-09b6-4129-8d8c-2d1278a12516
author: Shawn Edwards
created: 2026-03-07T05:20:03Z

I understand the issue: When users add comments to issues via the web UI, the comments are not being saved/displayed. My plan is to: 1) Explore the codebase to find the comment-related code, 2) Trace the flow from UI to backend, 3) Identify why comments aren't persisting, 4) Fix the root cause.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ed556143-1bfb-46cf-9e69-01f4e2852df4
author: testuser
created: 2026-03-07T05:20:54Z

test comment from agent investigation
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8acc43b1-5c63-41f8-8fb2-844e05ba4662
author: testuser2
created: 2026-03-07T05:23:17Z

Test comment from Python tracker
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d05fc438-939e-4ab2-960d-adb4a7c39785
author: agent
created: 2026-03-07T05:24:29Z

Found the root cause - investigating the project_id propagation in api_issue_full_detail
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9b351d06-15b3-4d94-b549-f01f76ea616c
author: agent
created: 2026-03-07T05:24:39Z

Found the bug: In api_issue_full_detail(), the response sets project_id from issue.project_id (which is None from bd output), instead of using the project_id from the request query param. This causes the frontend to lose the project context. When submitting a comment, the project_id is empty so the comment goes to the legacy tracker (wrong cwd) instead of the project-specific tracker. The comment is stored in the wrong database and is not visible when the detail panel refreshes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 18667aa5-cbac-4163-b554-6c770eadc300
author: test
created: 2026-03-07T05:27:55Z

test json output
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d320bcda-f0b4-4fe1-983d-434672197e38
author: test
created: 2026-03-07T05:28:02Z

test without json
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 44815af3-e69d-435f-95e7-70e9dd1095c6
author: oompah
created: 2026-03-07T05:28:55Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 97e8fe7f-ea8a-4763-8c10-32db0ab1b7cf
author: oompah
created: 2026-03-07T05:28:59Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f96fdffe-21f7-4c57-9941-e675d5360890
author: Shawn Edwards
created: 2026-03-07T05:29:38Z

I understand the issue: When users add comments to issues via the web UI, the comments are not being saved/displayed. A previous investigator found that project_id propagation may be involved. My plan is to: 1) Trace the full comment flow from UI to backend, 2) Confirm the root cause, 3) Apply a minimal fix, 4) Test.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7637a8dc-6028-4595-b9e9-fe2181791abe
author: Shawn Edwards
created: 2026-03-07T05:31:29Z

Found the bug: In api_issue_full_detail() (server.py line ~486), the response returns issue.project_id which is None (the bd tracker _normalize_issue doesn't set project_id). It should use the project_id from the request query parameter instead. This causes the frontend to lose project context, so when submitting a comment, it goes to the legacy tracker instead of the project-specific tracker. The comment gets stored in the wrong database and is invisible when the detail panel reloads.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2ce51957-9b25-4aa5-97b8-d46989588a8d
author: oompah
created: 2026-03-07T05:33:27Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10eaaa40-fe26-4fe5-8f23-4c339a953e08
author: oompah
created: 2026-03-07T05:33:32Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 181bbd44-d2d2-42cf-845b-e89886141aed
author: Shawn Edwards
created: 2026-03-07T05:34:03Z

I understand the issue: Comments added via the web UI are not being saved/displayed. Previous investigators found the root cause may be related to project_id propagation in api_issue_full_detail(). I'll trace the full comment flow from UI to backend, confirm the root cause, and apply a minimal fix.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: cd66bb09-3d97-47db-b037-c591267847b4
author: Shawn Edwards
created: 2026-03-07T05:36:02Z

Confirmed the root cause: In api_issue_full_detail() (server.py), the response returns issue.project_id which is None because _normalize_issue() doesn't populate project_id from bd output. The project_id query parameter IS correctly used to select the right tracker, but it's not propagated into the response. The frontend then stores an empty project_id, so when submitting a comment, it goes to the legacy tracker (wrong cwd) instead of the project-specific tracker. Fix: set issue.project_id = project_id in api_issue_full_detail() before building the response, mirroring what _fetch_all_issues() already does.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 88c0b62c-c86b-401f-8db9-ffdba3ad12b2
author: oompah
created: 2026-03-07T05:38:03Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3ac9003e-2e15-4618-839a-2d450466b14d
author: oompah
created: 2026-03-07T05:38:08Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 847eef32-a2d6-4a60-b11a-b7150aa4cefc
author: Shawn Edwards
created: 2026-03-07T05:38:22Z

I understand the issue: Comments added via the web UI are not being saved/displayed. Previous investigators identified the root cause as project_id not being propagated in api_issue_full_detail() response. I'll confirm this, apply the fix, and verify.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7230223f-9495-4f50-b3a6-fd4b46e62919
author: Shawn Edwards
created: 2026-03-07T05:42:32Z

Confirmed the root cause: In api_issue_full_detail(), the response returns issue.project_id which is always None because _normalize_issue() doesn't set it from bd output. The project_id query param is used correctly to get the right tracker, but it's not propagated into the response JSON. The frontend then stores empty project_id, and when submitting a comment, the comment goes to the legacy tracker (wrong database). Fix: set issue.project_id = project_id before building the response dict, matching what _fetch_all_issues() already does.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 328ac7d9-9b5f-4e0c-b286-19d01bca0bc5
author: Shawn Edwards
created: 2026-03-07T05:43:58Z

Implementation: Added project_id propagation in api_issue_full_detail(). Before building the response dict, if project_id query param is present, we set issue.project_id = project_id. This ensures the frontend receives the correct project context, so when submitting comments, the project_id is sent back and the comment is stored in the correct project-specific tracker.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 98fd773e-0e39-416f-90d7-61374ec3f26e
author: Shawn Edwards
created: 2026-03-07T05:44:06Z

Verification: All 185 passing tests still pass. The 1 pre-existing failure (test_blocked_by_dicts) is unrelated to this change — it fails on main as well.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
