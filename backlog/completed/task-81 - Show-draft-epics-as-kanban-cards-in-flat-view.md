---
id: TASK-81
title: Show draft epics as kanban cards in flat view
status: Done
assignee: []
created_date: 2026-03-08 18:04
updated_date: 2026-03-08 19:15
labels:
- archive:yes
- merged
- beads-migrated
dependencies:
- TASK-83
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-14u
  state: closed
  parent_id: oompah-7rw
  dependencies:
  - oompah-7e0
  branch_name: oompah-14u
  target_branch: null
  url: null
  created_at: '2026-03-08T18:04:23Z'
  updated_at: '2026-03-08T19:15:11Z'
  closed_at: '2026-03-08T19:15:11Z'
parent: TASK-76
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Modify the renderFlatView() function in oompah/templates/dashboard.html to include epics that have the 'draft' label as normal cards alongside tasks/bugs/features. Currently line ~1209 filters out ALL epics with: const issues = allInCol.filter(i => i.issue_type !== 'epic'). Change this to: const issues = allInCol.filter(i => i.issue_type !== 'epic' || (i.labels || []).includes('draft')). Also update createCard() to show a 'Draft Epic' badge (styled like merged-badge but in a distinct color, e.g. purple/accent) when a card is an epic with the draft label. The badge should be visible alongside the priority badge and issue ID. Non-draft epics should still be excluded from the flat view. Update the col-count to reflect only non-draft-epic cards. Add tests in tests/test_dashboard_draft_epics.py (can test the server-side data shape, or use pytest-playwright / snapshot tests if available). If no browser testing is set up, write unit tests for the server-side filtering logic in api_issues.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 26cfbe5d-f839-401f-9b05-4f908b7c26ef
author: oompah
created: 2026-03-08T19:07:18Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: eef002c5-ae54-4eef-b329-52dd6a890421
author: oompah
created: 2026-03-08T19:07:18Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8c320208-b00e-4fe5-9010-1d3355962d4e
author: Shawn Edwards
created: 2026-03-08T19:08:14Z

I understand the issue: The task is to write tests for the 'Show draft epics as kanban cards in flat view' feature. The implementation already exists in dashboard.html and the test file tests/test_dashboard_draft_epics.py is missing. My plan is to write comprehensive tests covering: (1) renderFlatView() includes draft epics (issue_type=epic with 'draft' label) while excluding non-draft epics, (2) the col-count reflects the filtered issues count, (3) createCard() generates the Draft Epic badge for draft epics, (4) server-side API data shape includes labels and issue_type so frontend can filter correctly. Tests will be in tests/test_dashboard_draft_epics.py and will exercise both the template JS (regex-parsed) and the Python server-side filtering logic.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5589f5a5-3642-41bb-b0ad-eb0ad589dd71
author: Shawn Edwards
created: 2026-03-08T19:08:34Z

Found the relevant code: (1) dashboard.html already has the renderFlatView() filter at line 1230 correctly including draft epics: 'const issues = allInCol.filter(i => i.issue_type !== epic || (i.labels || []).includes(draft))'. (2) createCard() at line 1437 generates the draftEpicBadgeHtml. (3) The .draft-epic-badge CSS class exists at line 335. (4) The API at /api/v1/issues serializes labels and issue_type for each issue. The test file tests/test_dashboard_draft_epics.py does not exist yet — I need to create it with comprehensive unit tests for all these behaviors.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1855af38-e87d-41e9-8ec3-6f289f451c17
author: Shawn Edwards
created: 2026-03-08T19:13:23Z

Implementation complete: Created tests/test_dashboard_draft_epics.py with 50 tests across 8 test classes covering: (1) renderFlatView() filter — verifies the exact expression 'filter(i => i.issue_type !== epic || (i.labels || []).includes(draft))', (2) col-count correctness — bound to filtered issues.length not allInCol.length, (3) createCard() Draft Epic badge — condition logic, HTML structure, CSS class, aria-label, placement in card-id-left, (4) .draft-epic-badge CSS — border-radius, font-size, font-family, padding, accent blue color not purple, (5) Server-side API data shape — labels and issue_type serialized correctly for frontend, (6) Edge cases — archived exclusion, task-with-draft-label, multi-label epics, empty set, (7) Regression guard — old broken filter detected, (8) Integration — API response shape supports frontend filter semantics. Added autouse cache-clearing fixture to prevent cross-test contamination.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a54e1786-0e14-4b27-bf55-cace0b2c13ac
author: Shawn Edwards
created: 2026-03-08T19:14:56Z

Verification: All 502 tests pass (50 new + 452 existing). Tests verified to fail when the old broken filter is present. PR created at https://github.com/lesserevil/oompah/pull/29
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dc6d62d2-0aff-4209-a464-31d4957b2755
author: Shawn Edwards
created: 2026-03-08T19:15:05Z

Completion: Delivered tests/test_dashboard_draft_epics.py with 50 tests covering all required behavior: (1) renderFlatView() filter expression allowing draft epics through while excluding plain epics, (2) col-count bound to filtered issues.length, (3) createCard() Draft Epic badge HTML/CSS/aria/placement, (4) .draft-epic-badge CSS distinctiveness from merged-badge, (5) server-side API data shape with labels/issue_type fields, (6) edge cases and regression guard against old broken filter. All 502 tests pass. PR: https://github.com/lesserevil/oompah/pull/29
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 71e6c6fd-4edb-4b0f-851f-3ac60316cbe3
author: oompah
created: 2026-03-08T19:15:12Z

Agent completed successfully in 474s (1787311 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
