---
id: TASK-83
title: Add 'Draft Epic' badge styling and card rendering
status: Done
assignee: []
created_date: 2026-03-08 18:04
updated_date: 2026-03-08 19:06
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-7e0
  state: closed
  parent_id: oompah-7rw
  dependencies: []
  branch_name: oompah-7e0
  target_branch: null
  url: null
  created_at: '2026-03-08T18:04:42Z'
  updated_at: '2026-03-08T19:06:55Z'
  closed_at: '2026-03-08T19:06:55Z'
parent: TASK-76
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add the CSS and HTML for a 'Draft Epic' badge shown on kanban cards that represent draft epics. In oompah/templates/dashboard.html: (1) Add a new CSS class '.draft-epic-badge' similar to '.merged-badge' but with a distinct color (e.g. use --accent blue or a new purple shade to distinguish from the epic-badge). (2) In the createCard() function, add logic to check if issue.issue_type === 'epic' && (issue.labels||[]).includes('draft') and if so inject the badge HTML. The badge text should be 'Draft Epic'. Place it in the card-id row alongside the merged-badge. (3) Ensure the card click handler for the id (openDetailPanel) works correctly for draft epic cards. (4) Ensure drag behavior works correctly — draft epics can be dragged between columns. Write tests that verify: the badge HTML generation logic, and that draft epics are draggable / movable.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 49374faa-4927-4c86-b25e-5383f39b0d70
author: oompah
created: 2026-03-08T19:02:26Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: af79a359-8771-4b8f-8a61-4762fcb7de04
author: oompah
created: 2026-03-08T19:02:27Z

Focus: Frontend Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 50a50f46-f99d-4a12-ba81-e47aab150ff1
author: Shawn Edwards
created: 2026-03-08T19:02:51Z

I understand the issue: Need to add a 'Draft Epic' badge to kanban cards in dashboard.html for issues where issue_type === 'epic' AND labels includes 'draft'. My plan: (1) Add .draft-epic-badge CSS class with a distinct blue/teal color to distinguish from .merged-badge (purple) and .epic-badge (purple). (2) Modify createCard() to check for draft epic condition and inject badge HTML in the card-id row. (3) Verify click handler and drag behavior work for draft epics (they should, since epics are rendered differently - but draft epics ARE shown as cards when they have the draft label). (4) Write tests following the pattern in test_collapsed_epics.py that verify badge HTML generation logic and draggability.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: eedb5214-9e4c-422c-bc51-8be103c217b9
author: Shawn Edwards
created: 2026-03-08T19:03:17Z

Found the relevant code: In dashboard.html, the .merged-badge and .epic-badge CSS classes are at lines ~315-340. The createCard() function is at line ~1375. The flat view filters out ALL epics at renderFlatView() (line ~1208). Draft epics need to: (1) Pass through the flat view filter (since they should appear as cards), (2) Show a 'Draft Epic' badge in the card-id row. Will add .draft-epic-badge CSS (blue/teal color to distinguish from purple merged-badge and epic-badge), update renderFlatView to pass through draft epics, and add badge generation in createCard().
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6528cda7-dc6c-4be1-91ef-bf8fcfb30563
author: Shawn Edwards
created: 2026-03-08T19:06:08Z

Implementation complete. Changes made to oompah/templates/dashboard.html: (1) Added .draft-epic-badge CSS class with --accent blue color (rgba(88,166,255,0.15) background, var(--accent) text) to distinguish from purple merged-badge and epic-badge. (2) Updated renderFlatView() filter to pass through draft epics (issue_type !== 'epic' || labels.includes('draft')). (3) Added draftEpicBadgeHtml logic in createCard() checking issue_type === 'epic' && labels.includes('draft'), injecting '<span class=draft-epic-badge aria-label=Draft Epic>Draft Epic</span>' in the card-id row alongside merged-badge. Card drag (draggable=true) and click handler (openDetailPanel) work for all cards including draft epics via existing createCard() infrastructure.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3bab6583-dfd3-4f1b-b5c2-8cbde93db8ea
author: Shawn Edwards
created: 2026-03-08T19:06:13Z

Tests verified: 25/25 new tests pass in tests/test_draft_epic_badge.py. Pre-existing failures (3 in test_collapsed_epics.py, 15 errors in test_projects_crud.py) are due to missing fastapi module, unrelated to this change. Full test suite: 402 passed, 3 failed (pre-existing), 15 errors (pre-existing).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 277f2625-58df-44e8-adcc-8da17c320cb0
author: Shawn Edwards
created: 2026-03-08T19:06:49Z

PR created: https://github.com/lesserevil/oompah/pull/25

Summary of deliverables:
1. CSS: .draft-epic-badge with --accent blue (distinct from purple merged-badge/epic-badge)
2. JS: renderFlatView() now shows draft epics as cards (not filtered out)
3. JS: createCard() generates 'Draft Epic' badge with aria-label when issue_type==='epic' && labels.includes('draft')
4. Drag behavior: works via existing card.draggable=true infrastructure
5. Click handler: openDetailPanel works for draft epics via existing setup
6. Tests: 25/25 passing in tests/test_draft_epic_badge.py
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 540353f8-2b1e-4cc2-b9b2-0100dd163f42
author: oompah
created: 2026-03-08T19:06:56Z

Agent completed successfully in 269s (1722441 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
