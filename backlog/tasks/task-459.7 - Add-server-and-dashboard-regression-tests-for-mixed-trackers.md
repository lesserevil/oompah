---
id: TASK-459.7
title: Add server and dashboard regression tests for mixed trackers
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 23:38'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.6
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-459
priority: medium
ordinal: 129000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cover mixed Backlog/GitHub issue lists, project filtering, detail panels, comments, labels, create flows, status updates, cache invalidation, and tracker identity display using mocked trackers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Mixed tracker board data cannot collide on bare task numbers.
- [ ] #2 All updated endpoints have GitHub-backed and Backlog-backed test cases.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 23:30
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 23:32
---
Understanding: As Duplicate Investigator, I searched for duplicates of this task (mixed trackers regression tests). No duplicate exists — this is a unique task in the TASK-459 epic series. TASK-459.6 (done) covered the create UI; this task is the regression test layer for ALL the mixed-tracker scenarios added across TASK-459.1-6. My investigation of existing tests shows these gaps: (1) No test exercises a board with BOTH Backlog and GitHub issues simultaneously; (2) AC#1 (identifier collision prevention) has no dedicated test; (3) Project filtering with mixed tracker types is not tested; (4) Cache invalidation patterns for mixed projects are not covered; (5) Status updates, comments, and label APIs for both tracker kinds lack side-by-side comparison tests. Plan: create tests/test_mixed_tracker_regression.py covering all AC items.
---

author: oompah
created: 2026-06-09 23:33
---
Discovery: No duplicate task exists. Code review complete. Key findings: (1) _fetch_and_serialize_issues() pulls from all projects in parallel; project_id is stamped on each issue. (2) _copy_issue_board() filters by project_id for project filtering. (3) _display_identifier() creates ProjectName-NNN for Backlog; display_identifier model field for GitHub. (4) _api_cache.invalidate('issues:all') is called after status update, comment, and label operations. (5) Tests gap confirmed: no test exercises both a Backlog tracker and a GitHub tracker simultaneously in the same board, no collision test, no mixed project-filter test, no cache invalidation test in the context of mixed trackers. Will create tests/test_mixed_tracker_regression.py.
---

author: oompah
created: 2026-06-09 23:38
---
Implementation: Created tests/test_mixed_tracker_regression.py with 46 new regression tests covering all task description scenarios: (1) TestMixedBoard — board contains both tracker kinds, project_id stamped on all entries, tracker_kind correct for each entry, all tracker keys present; (2) TestIdentifierCollisionPrevention — AC#1 verified: TASK-N and GitHub #N have distinct display_identifiers, uniqueness guaranteed within and across trackers, legacy variant; (3) TestProjectFiltering — filter_project correctly narrows to the requested tracker's project, no-filter returns all; (4) TestDetailPanelMixedTrackers — AC#2: backlog detail has null tracker_kind, github detail has populated fields, legacy is_legacy=true, all required keys present for both kinds; (5) TestCommentsMixedTrackers — AC#2: GET/POST comments for both tracker kinds, cross-tracker isolation test; (6) TestLabelsMixedTrackers — AC#2: add label for both kinds, cross-tracker isolation; (7) TestCreateFlowsMixedTrackers — AC#2: create routes to correct tracker, response includes correct tracker_kind; (8) TestStatusUpdatesMixedTrackers — AC#2: status and priority update for both kinds; (9) TestCacheInvalidationMixedTrackers — issues:all invalidated after status update, comment post, label add for both backlog and github; (10) TestTrackerIdentityDisplayBoard — URL fallback, provider_url, is_legacy, full tracker fields, priority sort on mixed board.
---

author: oompah
created: 2026-06-09 23:38
---
Verification: 46/46 new tests in test_mixed_tracker_regression.py pass. 313/313 tests in related test files (server_create_issue, server_issue_detail, server_issue_detail_api, server_label_api, backlog_tracker, tracker_protocol, shared_tracker_contract) pass. 135/135 tests in previously-added 459-series files (test_server_tracker_identity_schema, test_dashboard_github_issues, test_server_create_labels, test_dashboard_create_github) pass. No regressions found.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Created tests/test_mixed_tracker_regression.py with 46 regression tests covering all mixed-tracker scenarios from the task description. Test classes: TestMixedBoard (5 tests, board with both tracker kinds), TestIdentifierCollisionPrevention (6 tests, AC#1: TASK-N and GitHub #N never collide in display_identifier), TestProjectFiltering (3 tests, project filter with mixed trackers), TestDetailPanelMixedTrackers (4 tests, AC#2: detail endpoints for both kinds), TestCommentsMixedTrackers (5 tests, AC#2: GET/POST comments, cross-tracker isolation), TestLabelsMixedTrackers (3 tests, AC#2: add label, cross-tracker isolation), TestCreateFlowsMixedTrackers (4 tests, AC#2: create routes to correct tracker), TestStatusUpdatesMixedTrackers (4 tests, AC#2: status/priority updates), TestCacheInvalidationMixedTrackers (5 tests, issues:all invalidated after each mutation type for both tracker kinds), TestTrackerIdentityDisplayBoard (7 tests, tracker fields on board entries). 46/46 pass; no regressions in 313 related existing tests. Branch: epic-TASK-459.
<!-- SECTION:FINAL_SUMMARY:END -->
