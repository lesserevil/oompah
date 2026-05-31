---
id: TASK-88
title: Add Finalize/Mark-as-Draft toggle button to swimlane header
status: Done
assignee: []
created_date: 2026-03-08 19:08
updated_date: 2026-03-08 19:16
labels:
- archive:yes
- merged
- beads-migrated
dependencies:
- TASK-87
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-ude
  state: closed
  parent_id: oompah-6cd
  dependencies:
  - oompah-eqj
  branch_name: oompah-ude
  target_branch: null
  url: null
  created_at: '2026-03-08T19:08:43Z'
  updated_at: '2026-03-08T19:16:53Z'
  closed_at: '2026-03-08T19:16:53Z'
parent: TASK-77
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the swimlane view, add a toggle button in the swimlane header actions area. The button should show 'Finalize' for draft epics and 'Mark as Draft' for non-draft epics.

## Button Behavior

**For draft epics** (epic has 'draft' label):
- Button label: 'Finalize'
- On click: calls DELETE /api/v1/issues/{identifier}/labels/draft (removes 'draft' label), then calls PATCH /api/v1/issues/{identifier} with {status: 'deferred'} to set it to deferred
- After success: calls refreshBoard() to update the UI

**For non-draft epics** (epic does NOT have 'draft' label):
- Button label: 'Mark as Draft'
- On click: calls POST /api/v1/issues/{identifier}/labels with body {label: 'draft', project_id: ...}, then calls PATCH /api/v1/issues/{identifier} with {status: 'deferred'}
- After success: calls refreshBoard() to update the UI

## Implementation

1. In `renderSwimlaneView` (dashboard.html, around line 1299), inside the `.swimlane-actions` span, add the toggle button after the existing '+ Child' and 'Details' buttons.

2. Add a new async function `toggleEpicDraft(epicIdentifier, isDraft, projectId)` that:
   - If isDraft: DELETEs the 'draft' label, then PATCHes status to 'deferred'
   - If not isDraft: POSTs the 'draft' label, then PATCHes status to 'deferred'
   - Uses the existing label API: POST /api/v1/issues/{id}/labels and DELETE /api/v1/issues/{id}/labels/draft
   - Calls refreshBoard() after completion
   - Handles errors gracefully (logs to console)

3. Wire the button in the swimlane header template:
   ```
   const isDraft = (epic.labels || []).includes('draft');
   const draftBtnLabel = isDraft ? 'Finalize' : 'Mark as Draft';
   // In the template:
   <button onclick="event.stopPropagation(); toggleEpicDraft('${esc(epic.identifier)}', ${isDraft}, '${esc(epic.project_id || '')}')">
     ${draftBtnLabel}
   </button>
   ```

## API Endpoints (already implemented in oompah-5e0)

- POST /api/v1/issues/{identifier}/labels  — body: {label, project_id}
- DELETE /api/v1/issues/{identifier}/labels/{label} — query param: project_id
- PATCH /api/v1/issues/{identifier} — body: {status, project_id}

## Tests

Add test class `TestSwimlaneDraftToggleButton` in `tests/test_draft_swimlane_toggle.py` covering:
- `toggleEpicDraft` function exists in the script
- For draft epics: 'Finalize' button is rendered in the swimlane actions
- For non-draft epics: 'Mark as Draft' button is rendered in the swimlane actions
- Button calls `toggleEpicDraft` with correct arguments including isDraft flag
- Button calls `event.stopPropagation()`
- `toggleEpicDraft` calls DELETE for the draft label when isDraft is true
- `toggleEpicDraft` calls POST for the draft label when isDraft is false
- `toggleEpicDraft` sets status to 'deferred' in both cases
- `toggleEpicDraft` calls refreshBoard after completion

## Context

- `renderSwimlaneView` is in `oompah/templates/dashboard.html` around line 1279
- The label API and PATCH endpoints are tested in `tests/test_server_label_api.py`
- Follow patterns of other API calls in the script (e.g., `updateIssue` function)
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: f621c93e-70c6-4d75-96c2-7294b2209521
author: oompah
created: 2026-03-08T19:12:11Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 86970f4c-298e-4319-92cd-f62e2cdebd87
author: oompah
created: 2026-03-08T19:12:12Z

Focus: Frontend Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a863b206-f7ab-40cd-827a-953873433f18
author: Shawn Edwards
created: 2026-03-08T19:12:21Z

I understand the issue: Need to add a Finalize/Mark-as-Draft toggle button to the swimlane header in dashboard.html. The button shows 'Finalize' for draft epics and 'Mark as Draft' for non-draft epics. My plan is to: 1) Find the renderSwimlaneView function in dashboard.html, 2) Add the toggle button in the .swimlane-actions area, 3) Add a new async toggleEpicDraft() JS function, 4) Wire up the button with proper onclick handler, 5) Write tests in tests/test_draft_swimlane_toggle.py.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 82a69abb-d44a-4251-9d97-4c5a473494cc
author: Shawn Edwards
created: 2026-03-08T19:12:58Z

Found the relevant code: The swimlane header is at lines 1308-1321 in dashboard.html. The .swimlane-actions span at line 1313 has '+ Child' and 'Details' buttons where I need to add the toggle button. No toggleEpicDraft function exists yet - need to add it. The test file tests/test_draft_swimlane_toggle.py exists but contains the wrong content (draft badge tests) - need to replace it with the correct toggle button tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ac80094e-3380-466d-ab79-96a2cb0fb03c
author: Shawn Edwards
created: 2026-03-08T19:16:12Z

Implementation complete. Changes made: 1) Added toggleEpicDraft async function in dashboard.html that DELETEs 'draft' label when isDraft=true, POSTs 'draft' label when isDraft=false, PATCHes status to 'deferred' in both cases, calls refreshBoard() after completion, and uses try/catch for error handling. 2) Added toggle button to swimlane-actions span using an IIFE to compute isDraft and draftBtnLabel inline, with event.stopPropagation(), aria-label for accessibility, and correct toggleEpicDraft() call signature. 3) Replaced incorrect content in tests/test_draft_swimlane_toggle.py with 24 proper TestSwimlaneDraftToggleButton tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9f961f7e-f293-4f9e-8d99-4876d35c7fdf
author: Shawn Edwards
created: 2026-03-08T19:16:19Z

Tests passing: All 24 tests in TestSwimlaneDraftToggleButton pass. Also confirmed all 42 adjacent related tests (test_draft_epic_swimlane.py, test_draft_epic_badge.py) still pass — no regressions. Pre-existing failures in test_server_create_issue.py and test_server_label_api.py are due to missing fastapi module in the test environment and are unrelated to these changes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f7c9432f-a0c9-4994-a219-ab015e5885b9
author: Shawn Edwards
created: 2026-03-08T19:16:48Z

PR created: https://github.com/lesserevil/oompah/pull/30

Delivered: Finalize/Mark-as-Draft toggle button in swimlane header with toggleEpicDraft async function. All 24 tests pass, no regressions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2378748f-481e-442a-892d-78628c6727fb
author: oompah
created: 2026-03-08T19:16:54Z

Agent completed successfully in 283s (991712 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
