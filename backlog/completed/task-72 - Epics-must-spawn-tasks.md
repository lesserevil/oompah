---
id: TASK-72
title: Epics must spawn tasks
status: Done
assignee: []
created_date: 2026-03-08 17:35
updated_date: 2026-03-08 17:53
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-f63
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-f63
  target_branch: null
  url: null
  created_at: '2026-03-08T17:35:30Z'
  updated_at: '2026-03-08T17:53:20Z'
  closed_at: '2026-03-08T17:53:20Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When we add an Epic to the system, and put it in 'open', oompah must then make a plan for the epic and create new taksk/bugs/features/chores to implement the actions specified in the epic
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 14244394-3408-4009-a31e-ae62cb0ecb7f
author: oompah
created: 2026-03-08T17:45:58Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: abc3ee71-4bcf-4f72-8c6b-040ec3dc5478
author: oompah
created: 2026-03-08T17:45:58Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1952d4e4-5d2a-4f73-9508-92acfd80bd6e
author: oompah
created: 2026-03-08T17:46:27Z

Agent stalled 1 time(s) (29s (150951 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3e06da2e-2d61-4e1a-83a1-2abce88a7fee
author: oompah
created: 2026-03-08T17:46:37Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: cdb1545d-e070-4fe3-86dd-c60ce0060e3d
author: oompah
created: 2026-03-08T17:46:38Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b4b6d476-4812-45a5-969f-d01c4b266696
author: Shawn Edwards
created: 2026-03-08T17:47:12Z

I understand the issue: When an epic is set to 'open', the orchestrator should detect it and instead of dispatching a normal coding agent, it should plan the epic by creating child tasks/bugs/features/chores. My plan: (1) Currently _should_dispatch skips epics entirely. (2) Add epic planning logic to the tick cycle that detects open epics and dispatches them to the API agent with the existing 'epic_planner' focus. (3) The epic planner focus already exists in focus.py. (4) I need to create a new method that handles epic planning - fetching open epics, checking if they already have children, and dispatching planning agents for them.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4fa17d90-1a6a-4896-aa76-17e4e7888b09
author: Shawn Edwards
created: 2026-03-08T17:47:41Z

Discovery: The codebase has all the pieces in place but they're not connected. (1) There's already an 'epic_planner' focus in focus.py with the right role/rules. (2) The orchestrator's _should_dispatch() explicitly skips epics with 'if issue.issue_type == "epic": return False'. (3) The tracker has create_issue() and add_parent_child() methods. What's missing: the tick cycle needs to detect open epics that don't yet have children and dispatch them for planning (using the epic_planner focus). I'll add _plan_open_epics() to the orchestrator tick cycle.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 16b796b9-e749-479a-bf46-0a4547c598f6
author: Shawn Edwards
created: 2026-03-08T17:52:17Z

Implementation complete. Changes made: (1) Added _should_dispatch_epic() to orchestrator.py - determines if an epic needs planning by checking: active state, no existing children, not already running/claimed/retrying/completed, budget and slot availability. (2) Added _fetch_epic_children() - fetches children from tracker with graceful error handling. (3) Added _plan_open_epics() - filters candidates to find plannable epics. (4) Integrated into _tick() cycle as Part 4.1 - after normal dispatch, open epics without children are dispatched for planning. (5) The existing epic_planner focus (already in focus.py) handles the agent instructions. (6) Updated the _should_dispatch() comment to clarify epics are handled separately.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d2282780-53da-40c0-920b-f73704f0ef33
author: Shawn Edwards
created: 2026-03-08T17:52:23Z

Verification: All 326 tests pass (292 existing + 34 new). New tests cover: _should_dispatch_epic (15 tests for all guard conditions), _fetch_epic_children (4 tests), _plan_open_epics (6 tests), _should_dispatch still skips epics (2 tests), tick integration (3 tests), epic_planner focus selection (4 tests).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a180ffd3-dc76-44c7-814f-575a830820ab
author: Shawn Edwards
created: 2026-03-08T17:53:02Z

PR created: https://github.com/lesserevil/oompah/pull/20
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8050f5b6-8dc1-414f-8c14-6cc0b8659a33
author: oompah
created: 2026-03-08T17:53:21Z

Agent completed successfully in 404s (4201003 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
