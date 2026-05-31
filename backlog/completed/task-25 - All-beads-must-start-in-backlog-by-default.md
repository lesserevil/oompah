---
id: TASK-25
title: All beads must start in 'backlog' by default
status: Done
assignee: []
created_date: 2026-03-06 21:02
updated_date: 2026-03-06 22:35
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: umpah-9ls
  state: closed
  parent_id: null
  dependencies: []
  branch_name: umpah-9ls
  target_branch: null
  url: null
  created_at: '2026-03-06T21:02:42Z'
  updated_at: '2026-03-06T22:35:50Z'
  closed_at: '2026-03-06T22:35:50Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
There needs to be a way for beads to not start in 'backlog' (see the merge resolve workflow).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 3d8e152b-4eea-4e52-98c2-039bf07d2eb0
author: oompah
created: 2026-03-06T22:18:19Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0e1b5014-75e5-4806-a95c-b5257b00a9fa
author: oompah
created: 2026-03-06T22:18:23Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9b295afb-b08d-4092-a9ca-b49051d58127
author: Shawn Edwards
created: 2026-03-06T22:18:38Z

I understand the issue: Beads currently start in 'backlog' by default, but there needs to be a way to create beads that don't start in 'backlog' (e.g., for merge resolve workflows). My plan is to explore the codebase, find where beads are created and their initial state is set, and add a mechanism to specify a different starting state.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b577fffd-ae58-4073-b02e-c4d39ae66435
author: oompah
created: 2026-03-06T22:19:57Z

Agent stalled 1 time(s) (98s (35430 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b6ebaf18-a133-49c4-9ff9-0111eb757417
author: oompah
created: 2026-03-06T22:20:22Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bbe40ee7-5e0f-4946-b34e-3dae0779743c
author: oompah
created: 2026-03-06T22:20:26Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d20862fe-c22c-4d1c-8212-f3bfb518ab6f
author: Shawn Edwards
created: 2026-03-06T22:26:47Z

I understand the issue: Currently, beads created via the API (and by the bd CLI) start in 'open' status, which means the orchestrator immediately picks them up for dispatch. The requirement is: (1) Beads should start in 'backlog' (the 'deferred' state) by default, so they sit in the backlog column until manually moved to open. (2) There needs to be a way for specific workflows (like merge conflict resolution) to bypass this and create/set beads directly in 'open' state.

Key code locations:
- tracker.py: create_issue() doesn't set initial status — uses bd CLI default ('open')
- server.py: api_create_issue() creates issues without setting status
- server.py: _notify_conflict_on_bead() reopens beads to 'open' for merge conflicts (correct behavior)

Plan: (1) Update create_issue in tracker.py to accept an optional initial_status param, defaulting to 'deferred' (backlog). (2) Update the API create endpoint to accept optional status, defaulting to 'deferred'. (3) Keep the merge conflict reopen workflow setting status to 'open' (already correct). (4) Update tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 18e8d78c-13bd-4854-a5ca-97b4920bdeea
author: Shawn Edwards
created: 2026-03-06T22:33:05Z

Implementation complete. Changes made:

1. **oompah/tracker.py**: Added DEFAULT_INITIAL_STATUS = 'deferred' constant. Updated create_issue() with an optional initial_status parameter (defaults to 'deferred'). After bd create (which always creates in 'open'), the method now updates the status to the target initial_status if different.

2. **oompah/server.py**: Updated api_create_issue() to pass body.get('status') as initial_status to create_issue(). When no status is provided in the API request, the default 'deferred' kicks in. Callers that need immediate dispatch (e.g., merge conflict resolution) can pass status='open'.

3. **tests/test_tracker.py**: Added 6 new tests covering: default to deferred, explicit open skips update, explicit deferred, custom status, and no-update-when-already-matching.

The merge conflict workflow in _notify_conflict_on_bead() already uses reopen_issue() which sets status to 'open', so it's unaffected and will correctly bypass backlog.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3bff47a9-8145-42ca-8f9c-8d46df6e0fcc
author: Shawn Edwards
created: 2026-03-06T22:33:23Z

Verification: All 171 tests pass (6 new + 165 existing). No regressions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a0f77afa-91b6-49d6-9b77-d6ce7d655d12
author: Shawn Edwards
created: 2026-03-06T22:35:37Z

PR created: https://github.com/lesserevil/oompah/pull/8 — Beads now default to backlog (deferred). API supports status override for workflows like merge conflict resolution. All 171 tests pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 27365822-e7fb-4306-b106-bac00c67fd16
author: oompah
created: 2026-03-06T22:36:04Z

Agent completed successfully in 943s (3565897 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
