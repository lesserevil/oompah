---
id: TASK-86
title: Cards must have a visual indicator of type
status: Done
assignee: []
created_date: 2026-03-08 19:01
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
  id: oompah-fpm
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-fpm
  target_branch: null
  url: null
  created_at: '2026-03-08T19:01:23Z'
  updated_at: '2026-03-08T19:06:02Z'
  closed_at: '2026-03-08T19:06:02Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
We need some kind of icon or image on each card to signify the card is a feature/epic/task/bug/chore.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: a9be9966-8660-4200-bf71-51ea123dc1e4
author: oompah
created: 2026-03-08T19:01:54Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: aefe0a0d-136c-4193-b14c-e28539b3c9bd
author: oompah
created: 2026-03-08T19:01:54Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2b5b885a-a5bc-4cc9-a754-0f3ae2f58ac8
author: Shawn Edwards
created: 2026-03-08T19:02:03Z

I understand the issue: Each card in the UI needs a visual indicator (icon or image) to show what type it is (feature/epic/task/bug/chore). My plan is to: 1) Explore the codebase to find where cards are rendered, 2) Find or create type-to-icon mappings, 3) Add the visual indicator to the card rendering, 4) Write tests to verify the indicator appears correctly.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 78b24127-54d9-412c-875d-f7fcb2ccd88c
author: Shawn Edwards
created: 2026-03-08T19:02:29Z

Found the relevant code: The card UI is built in oompah/templates/dashboard.html in the createCard() JavaScript function (around line 1376). Currently, cards show an identifier, priority badge, epic badge, and merged badge, but no visual indicator for the issue type (feature/epic/task/bug/chore). I need to: 1) Define type-to-emoji/icon mappings in CSS and JS, 2) Add a type indicator element to the card-id row in createCard(), and 3) Add a CSS style for the type icon. The test pattern from tests/test_server_edit_protection.py shows the approach for verifying dashboard JS changes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b0ecbfa3-5ceb-445d-a90e-d71831d04970
author: Shawn Edwards
created: 2026-03-08T19:05:24Z

Implementation complete. Changes made to oompah/templates/dashboard.html: 1) Added .type-icon CSS class for consistent icon sizing, 2) Added TYPE_ICONS constant mapping feature/epic/task/bug/chore to emoji icons (✨/🗺️/✅/🐛/🔧) with 📋 fallback, 3) Added getTypeIcon() helper function, 4) Added <span class='type-icon'> element to each card's card-id section showing the issue type icon with a tooltip title attribute, 5) Added .card-identifier class to the ID span so the click handler can find it correctly after the type-icon was prepended. Also created tests/test_card_type_indicator.py with 19 tests covering all aspects of the feature.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9b244179-1dd4-4dcb-838f-547924ca5646
author: Shawn Edwards
created: 2026-03-08T19:05:58Z

PR created: https://github.com/lesserevil/oompah/pull/24

Verification results: 19 new tests all pass, 11 existing edit-protection tests still pass, no pre-existing passing tests broken.

Summary of what was delivered:
- Each kanban card now shows an emoji icon indicating its type: ✨ feature, 🗺️ epic, ✅ task, 🐛 bug, 🔧 chore, 📋 fallback
- Icon appears in the card header before the identifier, with title/aria-label for accessibility
- TYPE_ICONS constant and getTypeIcon() function added to dashboard JS
- .type-icon CSS class added for consistent sizing
- .card-identifier class added to fix click handler selector after inserting icon before it
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d255d168-f0b9-47b6-8fc4-16b762cae31e
author: oompah
created: 2026-03-08T19:06:03Z

Agent completed successfully in 249s (1102287 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
