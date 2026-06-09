---
id: TASK-459.7
title: Add server and dashboard regression tests for mixed trackers
status: In Progress
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 23:33'
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
<!-- COMMENTS:END -->
