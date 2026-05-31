---
id: TASK-115
title: Switching between 'flat' and 'swimlanes' messes with the card column headings
status: Done
assignee: []
created_date: 2026-03-09 05:48
updated_date: 2026-03-09 06:03
labels:
- archive:yes
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-8h6
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-8h6
  target_branch: null
  url: null
  created_at: '2026-03-09T05:48:51Z'
  updated_at: '2026-03-09T06:03:21Z'
  closed_at: '2026-03-09T06:03:21Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->

<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 3c99132e-3979-4ef9-a3f1-c5688fe0340d
author: oompah
created: 2026-03-09T05:49:37Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 59b410aa-d240-467d-b4c4-44036f6cb9c8
author: oompah
created: 2026-03-09T05:49:38Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c0640b41-346e-4b7f-b52e-8cf478e1624e
author: oompah
created: 2026-03-09T05:51:17Z

I understand the issue: When switching between 'flat' and 'swimlanes' view modes, the card column headings get messed up. My plan is to investigate the renderFlatView and renderSwimlaneView functions in dashboard.html to find what causes column headings to break when toggling between views, then implement a fix and write tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 110c7075-ec43-4715-b2f2-ba28ce65cb4d
author: oompah
created: 2026-03-09T05:58:18Z

Found the bug: In swimlane view, each swimlane row creates its own set of column headers ('Backlog', 'Open', 'In Progress', 'Closed'), causing them to repeat for every epic. When switching between flat (4 global column headers) and swimlane view (N×4 repeated column headers), the visual appearance of column headings changes jarringly. The fix: show column headers once at the top of the board in swimlane view (sticky header row), and hide per-swimlane column headers via CSS.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 38854b3b-f93e-4b79-8bd8-bd59c4e62abc
author: oompah
created: 2026-03-09T06:01:50Z

Implementation complete. Changes to oompah/templates/dashboard.html: (1) Added CSS rule '.swimlane-columns .column-header { display: none; }' to hide the repeated column headers inside each swimlane row. (2) Added '.swimlane-board-header' CSS class for a sticky header strip at the top of the swimlane board. (3) In renderSwimlaneView(), added code to create and prepend a single '.swimlane-board-header' element with 'Backlog / Open / In Progress / Closed' labels before the swimlane rows. In flat view, the existing column headers remain unchanged. This ensures column headings appear exactly once in both views and switching between views is no longer visually jarring.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 39e6ed17-5067-4932-88d0-5ab404bf96fa
author: oompah
created: 2026-03-09T06:03:16Z

All 19 tests pass. Changes pushed to branch oompah-8h6. Summary: Fixed column headings appearing N times in swimlane view (once per epic) by (1) hiding per-swimlane .column-header via CSS, (2) adding a single sticky .swimlane-board-header with column labels at the top of the swimlane board, (3) updating renderSwimlaneView() to prepend this header. Flat view is unchanged.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3665de46-91eb-432c-81af-2e24a6f42fae
author: oompah
created: 2026-03-09T06:03:36Z

Agent completed successfully in 839s (4283663 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
