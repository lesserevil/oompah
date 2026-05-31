---
id: TASK-85
title: Collapsed closed epics in swimlane view
status: Done
assignee: []
created_date: 2026-03-08 18:14
updated_date: 2026-03-08 18:21
labels:
- archive:yes
- merged
- feature
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: feature
beads:
  id: oompah-mus
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-mus
  target_branch: null
  url: null
  created_at: '2026-03-08T18:14:48Z'
  updated_at: '2026-03-08T18:21:01Z'
  closed_at: '2026-03-08T18:21:01Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
By default, 'unopened' epics (epics with no issues in backlog, open, or in progress) in the swimlane view should be 'collapsed'. This will draw attention to the epics with active and potential work.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 3e5a8f38-0745-45ea-bfed-f9456ce24806
author: oompah
created: 2026-03-08T18:15:21Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c880f39a-dc88-45e2-a0f6-fc889b1205f1
author: oompah
created: 2026-03-08T18:15:22Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1d7c7b44-9e2e-443b-95f3-20589ea0a1d4
author: oompah
created: 2026-03-08T18:15:46Z

Agent stalled 1 time(s) (25s (57545 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f8d19c10-9595-429a-b990-e2ec7db568eb
author: oompah
created: 2026-03-08T18:15:56Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b06af503-4db8-4c54-a170-388b34ca7b77
author: oompah
created: 2026-03-08T18:15:57Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7d471c1d-e40b-47b4-b955-9dea0c8bd7ff
author: Shawn Edwards
created: 2026-03-08T18:16:33Z

I understand the issue: In the swimlane view, epics that have no active or potential work (i.e., no issues in backlog/open/in_progress states) should be collapsed by default. Currently, all swimlanes start expanded. My plan: 1) In renderSwimlaneView(), check each epic's children_counts and auto-collapse if all non-closed counts are 0, 2) Initialize collapsedSwimlanes accordingly on each render, 3) Write tests to verify the logic.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fbc588d0-0795-4da1-8fc5-71e6a6aa1ce5
author: Shawn Edwards
created: 2026-03-08T18:16:56Z

Found the key code. The renderSwimlaneView() function in dashboard.html renders each epic as a swimlane. Currently collapsedSwimlanes is just a plain object {}. The fix: before rendering, auto-collapse epics that have no active children (backlog/open/in_progress counts all 0). User manual toggles should override auto-collapse. Also noticed _fetch_and_serialize_issues (used for WebSocket broadcast) doesn't include children_counts - need to fix that too so the auto-collapse logic works with WebSocket data.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 76f52e4f-f947-4ced-ab42-00c5d33ed4f8
author: Shawn Edwards
created: 2026-03-08T18:20:12Z

Implementation complete. Changes made:

1. **dashboard.html**: Added isEpicInactive() helper that checks if an epic has no children in backlog/open/in_progress. Added userToggledSwimlanes tracking object. Modified renderSwimlaneView() to auto-collapse inactive epics unless the user has explicitly toggled them. Modified toggleSwimlane() to record user intent.

2. **server.py**: Updated _fetch_and_serialize_issues() (WebSocket broadcast path) to compute and include children_counts for epics, matching the existing api_issues REST endpoint behavior. This ensures swimlane auto-collapse works with real-time WebSocket data.

3. **tests/test_collapsed_epics.py**: 16 new tests across 5 test classes covering: isEpicInactive function correctness, userToggledSwimlanes tracking, auto-collapse integration in renderSwimlaneView, collapsedSwimlanes sync-back, and server-side children_counts in WebSocket serialization.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 50a7da56-b849-4ba0-8dac-189578a07c83
author: Shawn Edwards
created: 2026-03-08T18:20:18Z

All 395 tests pass (16 new + 379 existing). No regressions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a3606ee9-e84b-47ed-b5cf-040b2684265e
author: Shawn Edwards
created: 2026-03-08T18:20:55Z

PR created: https://github.com/lesserevil/oompah/pull/22
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b0750bba-0686-456f-9906-08c34f8ead84
author: oompah
created: 2026-03-08T18:21:02Z

Agent completed successfully in 306s (2120517 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
