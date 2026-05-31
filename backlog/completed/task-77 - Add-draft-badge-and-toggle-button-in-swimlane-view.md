---
id: TASK-77
title: Add draft badge and toggle button in swimlane view
status: Done
assignee: []
created_date: 2026-03-08 18:02
updated_date: 2026-03-08 19:24
labels:
- archive:yes
- beads-migrated
dependencies:
- TASK-80
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-6cd
  state: closed
  parent_id: oompah-7rw
  dependencies:
  - oompah-5e0
  branch_name: oompah-6cd
  target_branch: null
  url: null
  created_at: '2026-03-08T18:02:44Z'
  updated_at: '2026-03-08T19:24:51Z'
  closed_at: '2026-03-08T19:24:51Z'
parent: TASK-76
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the swimlane view, add a 'Draft' badge next to draft epic titles. Add a toggle button in the swimlane header actions: 'Finalize' for draft epics (removes draft label, sets status to deferred) and 'Mark as Draft' for non-draft epics (adds draft label, moves to deferred so it re-enters the kanban). Wire these to the existing label add/remove API endpoints.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 2cf40daa-6c4e-4959-80a4-c3395c622485
author: oompah
created: 2026-03-08T19:07:16Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8d1ae3f0-da20-46c2-a5c1-2b945a449c54
author: oompah
created: 2026-03-08T19:07:17Z

Focus: Epic Planner
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0cd315c5-0cf8-4030-9243-6be6fd7abe44
author: Shawn Edwards
created: 2026-03-08T19:08:00Z

I understand the issue: Add a 'Draft' badge next to draft epic titles in the swimlane header, and add a toggle button ('Finalize' for drafts / 'Mark as Draft' for non-drafts) in the swimlane actions. These buttons should call the existing label API endpoints (POST /api/v1/issues/{id}/labels and DELETE /api/v1/issues/{id}/labels/{label}) to add/remove the 'draft' label and update the epic status to 'deferred'.

My plan is to decompose this into 3 child tasks:
1. Add Draft badge in swimlane header — render a visual badge next to the epic title when the epic has the 'draft' label
2. Add Finalize/Mark-as-Draft toggle button in swimlane header actions — the button logic and API wiring
3. Add tests for the swimlane draft badge and toggle button

The label API endpoints already exist (implemented in oompah-5e0). The Draft badge on cards already exists (in createCard()). What's missing is the swimlane header badge and the toggle button.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c63dfb19-4a68-4961-aedf-41b1f1c0d92f
author: oompah
created: 2026-03-08T19:12:11Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f409f06a-a18d-489c-9fec-fd5a09923d22
author: oompah
created: 2026-03-08T19:12:12Z

Focus: Epic Planner
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: eb80db21-b633-4c87-80ce-20e32d974b8b
author: Shawn Edwards
created: 2026-03-08T19:12:34Z

I understand the issue: The swimlane view needs (1) a 'Draft' badge next to epic titles when the epic has the 'draft' label, and (2) a toggle button ('Finalize' for drafts / 'Mark as Draft' for non-drafts) wired to the label API endpoints.

Planning is already complete from the previous agent session. Two child tasks were created:
- oompah-eqj (CLOSED): Draft badge in swimlane header — already implemented and merged (PR #28)
- oompah-ude (IN_PROGRESS): Finalize/Mark-as-Draft toggle button — currently being implemented

Both tasks cover the full scope of this epic. No additional tasks needed. Marking epic as deferred.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 71e44476-4b1e-4c04-ac0b-8c644574f44d
author: oompah
created: 2026-03-08T19:17:37Z

Focus: Epic Planner
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7eb9dca8-a92e-447a-9021-3d768708397a
author: oompah
created: 2026-03-08T19:17:37Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: cb2d85df-75dc-4afe-b332-c5835672a329
author: Shawn Edwards
created: 2026-03-08T19:17:51Z

I understand the issue: The swimlane view needs (1) a Draft badge next to epic titles when the epic has the draft label, and (2) a toggle button (Finalize for drafts / Mark as Draft for non-drafts) wired to the label API endpoints.

Reviewing the current state: Both child tasks are already CLOSED:
- oompah-eqj (CLOSED): Draft badge in swimlane header — implemented and merged (PR #28)
- oompah-ude (CLOSED): Finalize/Mark-as-Draft toggle button — implemented and closed (PR #30)

All work is complete. The epic just needs to be finalized — removing the draft label (none present) and setting status to deferred.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b1e87d84-1bed-4d41-b70c-2153fe986c39
author: Shawn Edwards
created: 2026-03-08T19:18:00Z

Planning complete. All child tasks were already implemented and closed by previous agents:
- oompah-eqj: Draft badge in swimlane header (CLOSED, PR #28)
- oompah-ude: Finalize/Mark-as-Draft toggle button (CLOSED, PR #30)

Both tasks cover the full scope of this epic. Epic status set to deferred, draft label removed.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3f087246-3417-4a7e-9a42-e183d6bb6b05
author: oompah
created: 2026-03-08T19:24:00Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ea788eb5-6ce6-468c-b47a-7faeac112dc7
author: oompah
created: 2026-03-08T19:24:00Z

Focus: Epic Planner
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f1a79c53-733b-4d69-95f6-3d6a666ba605
author: Shawn Edwards
created: 2026-03-08T19:24:11Z

I understand the issue: The swimlane view needs (1) a Draft badge next to epic titles when the epic has the draft label, and (2) a toggle button (Finalize for drafts / Mark as Draft for non-drafts) wired to the label API endpoints.

Reviewing current state: Both child tasks are already CLOSED:
- oompah-eqj (CLOSED): Draft badge in swimlane header — implemented and merged (PR #28)
- oompah-ude (CLOSED): Finalize/Mark-as-Draft toggle button — implemented and closed (PR #30)

All work is complete. The full scope of the epic has been delivered. Setting epic status to deferred to reflect completion of planning and implementation.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a8dd0ad3-4694-4d04-9e88-b6084b9fab8f
author: Shawn Edwards
created: 2026-03-08T19:24:23Z

Planning complete. All child tasks were already implemented and closed by previous agents:
- oompah-eqj: Draft badge in swimlane header (CLOSED, PR #28)
- oompah-ude: Finalize/Mark-as-Draft toggle button (CLOSED, PR #30)

Both tasks cover the full scope of this epic. Epic status set to deferred.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b2c2bb5b-53e4-49b7-81e5-f6e35f892e02
author: oompah
created: 2026-03-08T19:24:30Z

Agent completed successfully in 31s (61998 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0f6fa995-4f5f-40da-bc6e-741ed07692ad
author: oompah
created: 2026-03-08T19:24:32Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 93980f5f-e6e6-4eb3-9ac9-ac3d091d3c5c
author: oompah
created: 2026-03-08T19:24:32Z

Focus: Epic Planner
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1e1652a7-3fcf-4913-a5b3-1fe1a28fbc45
author: Shawn Edwards
created: 2026-03-08T19:24:48Z

Planning complete. All child tasks have been implemented and closed by previous agents:
- oompah-eqj (CLOSED): Draft badge in swimlane header — implemented and merged (PR #28)
- oompah-ude (CLOSED): Finalize/Mark-as-Draft toggle button — implemented and closed (PR #30)

Both tasks cover the full scope of this epic. No additional tasks needed. Epic status set to deferred.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 640bc2b1-92d8-45a3-a592-18228744c079
author: oompah
created: 2026-03-08T19:24:58Z

Agent completed successfully in 26s (53405 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
