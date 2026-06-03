---
id: TASK-427
title: '[backend:server] Update issue API error: backlog command failed (exit 1):
  Task TASK-167 not found.'
status: In Progress
assignee: []
created_date: 2026-06-03 00:33
updated_date: 2026-06-03 05:27
labels:
- bug
dependencies: []
priority: medium
ordinal: 61000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update issue API error: backlog command failed (exit 1): Task TASK-167 not found.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 05:12

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 05:20

Discovery: TASK-427 is NOT a duplicate of TASK-405 or TASK-417. Root cause: TASK-167 is in backlog/completed/ (status: Done). When update_issue is called with this identifier, the backlog CLI runs "backlog task edit TASK-167" but CLI only looks in tasks/ not completed/, so it exits 1 with "Task TASK-167 not found.". Fix: in update_issue(), catch TrackerError with "not found", check if task exists on disk via _task_path_for(), and fall back to direct frontmatter editing via new _update_issue_fields_direct() method.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-03 05:26

Implementation: Added _update_issue_fields_direct() method and modified update_issue() in oompah/tracker.py. When the Backlog CLI raises TrackerError with 'not found' in the message, update_issue() now checks if the task exists on disk via _task_path_for(). If found (e.g. in completed/), it falls back to direct frontmatter/body editing. Also added helper _is_task_not_found_error(). 7 new regression tests in tests/test_backlog_tracker.py all pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 05:27

Verification: All 33 tests in tests/test_backlog_tracker.py pass, including 7 new regression tests. Also verified with 175 passing tests across test_backlog_tracker, test_backlog_compat, test_error_watcher, test_backlog_webhooks, and test_dispatch_close_race. Fix confirmed: update_issue now silently falls back to direct file editing when Backlog CLI cannot find a task in completed/.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
