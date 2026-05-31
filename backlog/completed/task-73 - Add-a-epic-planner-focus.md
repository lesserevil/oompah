---
id: TASK-73
title: Add a 'epic planner' focus
status: Done
assignee: []
created_date: 2026-03-08 17:37
updated_date: 2026-03-08 17:41
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-e1i
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-e1i
  target_branch: null
  url: null
  created_at: '2026-03-08T17:37:03Z'
  updated_at: '2026-03-08T17:41:18Z'
  closed_at: '2026-03-08T17:41:18Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
We need a focus specifically created for filling out the tasks within epics.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 2a1bbef5-7448-48f9-bcc6-38ad6a9f6454
author: oompah
created: 2026-03-08T17:37:15Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0c3e6ef1-dc7d-4639-8f99-e748d991b6bf
author: oompah
created: 2026-03-08T17:37:16Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bc7a07c6-5555-4dde-a4ad-f7665ad150b8
author: Shawn Edwards
created: 2026-03-08T17:38:13Z

I understand the issue: We need to add an 'epic planner' focus to the BUILTIN_FOCI list in oompah/focus.py. This focus is for an agent specialized in filling out tasks within epics — decomposing an epic issue into its constituent sub-tasks/issues. My plan is to: 1) Add a new Focus named 'epic_planner' to the BUILTIN_FOCI list with appropriate keywords (epic, epic planner, breakdown, tasks, subtasks), must_do/must_not_do rules, and issue_types; 2) Add corresponding tests in tests/test_focus.py to verify the focus is selected correctly.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a682e434-f2d3-4615-a981-550ed5cd2857
author: Shawn Edwards
created: 2026-03-08T17:38:54Z

Found the relevant code: oompah/focus.py contains BUILTIN_FOCI list (around line 90). The orchestrator currently skips epics in dispatch, but the issue just asks for the focus definition to be available. I'll add a new 'epic_planner' Focus to BUILTIN_FOCI with: keywords matching epic/plan/breakdown/decompose, issue_types=['epic'], role='Epic Planner', and appropriate must_do/must_not_do rules for creating well-structured sub-tasks.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5adff44e-649c-49ae-b916-a615ddd79ee3
author: Shawn Edwards
created: 2026-03-08T17:40:32Z

Implementation: Added the 'epic_planner' focus to BUILTIN_FOCI in oompah/focus.py. The focus has: role='Epic Planner', issue_types=['epic'], keywords=['epic', 'plan', 'planning', 'breakdown', 'decompose', 'tasks', 'subtasks', 'milestones'], priority=8, with 6 must_do rules (read epic before creating tasks, create concrete/actionable tasks, provide context in each task, cover full scope, set dependencies, use bd create) and 5 must_not_do rules (no coding, no oversized tasks, no undescribed tasks, no duplicates, don't close epic yourself). Also added 16 tests in tests/test_focus.py in a TestEpicPlannerFocus class.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7d42d475-114c-4e93-853b-89e8b308243e
author: Shawn Edwards
created: 2026-03-08T17:40:39Z

Verification: All 61 tests in test_focus.py pass (45 existing + 16 new). Full suite shows 321 passed, 8 warnings, 15 pre-existing errors in test_projects_crud.py::TestProjectAPI due to missing fastapi module (unrelated to this change).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ea530e4a-891b-4ad2-8cf7-374ca8985a37
author: Shawn Edwards
created: 2026-03-08T17:41:13Z

Completion: PR created at https://github.com/lesserevil/oompah/pull/19. Delivered: new 'epic_planner' focus in BUILTIN_FOCI (oompah/focus.py) with role='Epic Planner', issue_types=['epic'], 8 priority, 6 must-do rules for decomposing epics into tasks, 5 must-not-do rules preventing scope creep. 16 new tests all passing.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7a1a7c5a-68d5-4964-8a23-0d2f090ee762
author: oompah
created: 2026-03-08T17:41:19Z

Agent completed successfully in 244s (1404964 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
