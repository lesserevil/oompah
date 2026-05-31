---
id: TASK-87
title: Add Draft badge to swimlane header for draft epics
status: Done
assignee: []
created_date: 2026-03-08 19:08
updated_date: 2026-03-08 19:11
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-eqj
  state: closed
  parent_id: oompah-6cd
  dependencies: []
  branch_name: oompah-eqj
  target_branch: null
  url: null
  created_at: '2026-03-08T19:08:24Z'
  updated_at: '2026-03-08T19:11:32Z'
  closed_at: '2026-03-08T19:11:32Z'
parent: TASK-77
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the swimlane view (renderSwimlaneView function in dashboard.html), add a 'Draft' badge next to the epic title in the swimlane header when the epic has the 'draft' label.

## What to do

In the `renderSwimlaneView` function (around line 1295), inside the swimlane header `lane.innerHTML` template literal, add conditional badge HTML between the `swimlane-title` span and the `swimlane-counts` span. The badge should:

- Only appear when `(epic.labels || []).includes('draft')` is true
- Use a new CSS class `.swimlane-draft-badge` (distinct from `.draft-epic-badge` on cards)
- Display the text 'Draft'
- Have an `aria-label='Draft epic'`
- Use the blue/accent color scheme (consistent with `.draft-epic-badge`)

## CSS

Add a `.swimlane-draft-badge` CSS rule near the existing `.draft-epic-badge` rule (around line 335). It should use similar styling but may be slightly larger to match the swimlane header scale.

## Tests

Add test class `TestSwimlaneDraftBadge` in `tests/test_draft_swimlane_toggle.py` covering:
- `.swimlane-draft-badge` CSS class exists in the HTML
- Badge HTML is generated in `renderSwimlaneView` when epic has 'draft' label
- Badge is NOT generated when epic does not have 'draft' label
- Badge uses `.swimlane-draft-badge` CSS class
- Badge text is 'Draft'

## Context

- The label API endpoints already exist (POST/DELETE /api/v1/issues/{id}/labels)
- The `renderSwimlaneView` is in `oompah/templates/dashboard.html` around line 1279
- The draft badge on cards (`.draft-epic-badge`) is separate from this swimlane header badge
- See `tests/test_draft_epic_badge.py` for the pattern to follow
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: cfb9b62c-bbd3-480d-af36-81538dc74566
author: oompah
created: 2026-03-08T19:08:54Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d355cc53-2795-4ce5-b8a8-7e07ffe5a91d
author: oompah
created: 2026-03-08T19:08:54Z

Focus: Frontend Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 32ed6a13-4f98-4bcf-8ed3-f6f834a1faf6
author: Shawn Edwards
created: 2026-03-08T19:09:02Z

I understand the issue: I need to add a 'Draft' badge to the swimlane header in renderSwimlaneView (dashboard.html) when an epic has the 'draft' label. My plan is to: 1) Find the relevant CSS rule (.draft-epic-badge) and add a .swimlane-draft-badge rule nearby, 2) Add the badge HTML in the lane.innerHTML template literal, 3) Create tests/test_draft_swimlane_toggle.py with TestSwimlaneDraftBadge class covering the required test cases.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dccd4b90-4523-487b-b341-1869f491ad58
author: Shawn Edwards
created: 2026-03-08T19:09:15Z

Found the key code: The .draft-epic-badge CSS is at line 335 of dashboard.html. The swimlane header innerHTML template is at line 1294-1304. I need to: 1) Add .swimlane-draft-badge CSS rule after .draft-epic-badge, 2) Add conditional badge HTML between the swimlane-title and swimlane-counts spans using (epic.labels || []).includes('draft').
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8082b4d7-b267-4ce6-96bb-a625ee5bb68e
author: Shawn Edwards
created: 2026-03-08T19:10:19Z

Implementation complete: 1) Added .swimlane-draft-badge CSS rule (slightly larger than .draft-epic-badge at 0.7rem) after the .draft-epic-badge rule using same blue/accent color scheme. 2) Added conditional badge HTML in renderSwimlaneView lane.innerHTML template between swimlane-title and swimlane-counts using (epic.labels || []).includes('draft') ternary. 3) Badge has aria-label='Draft epic' for accessibility. 4) Created tests/test_draft_swimlane_toggle.py with TestSwimlaneDraftBadge covering all required cases.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dcd09193-2248-4771-9c04-42cc8ffafb16
author: Shawn Edwards
created: 2026-03-08T19:11:00Z

Verification: All 10 new tests in TestSwimlaneDraftBadge pass. All 25 existing tests in test_draft_epic_badge.py also pass (35 total). Pre-existing failures in test_server_label_api.py and test_collapsed_epics.py are unrelated (missing fastapi module, not introduced by this change).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1b928383-3dd6-4aa5-b64b-3bb299c9bdf8
author: Shawn Edwards
created: 2026-03-08T19:11:28Z

PR created: https://github.com/lesserevil/oompah/pull/28

Summary of deliverables:
- CSS: Added .swimlane-draft-badge rule (blue/accent, 0.7rem) in dashboard.html near .draft-epic-badge
- JS: Added conditional Draft badge in renderSwimlaneView lane.innerHTML template between title and counts spans, with aria-label='Draft epic' and null-safe (epic.labels || []).includes('draft') check
- Tests: 10 new tests in TestSwimlaneDraftBadge in tests/test_draft_swimlane_toggle.py, all passing
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 080c45e1-7dac-4090-a70c-bac2ff840239
author: oompah
created: 2026-03-08T19:11:33Z

Agent completed successfully in 159s (367157 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
