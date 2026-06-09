---
id: TASK-466.6
title: 'CI fix: PR #244 on branch epic-TASK-466'
status: Open
assignee: []
created_date: '2026-06-09 03:19'
updated_date: '2026-06-09 03:33'
labels: []
dependencies: []
parent_task_id: TASK-466
ordinal: 185000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
YOLO: CI tests failed on MR #244 (branch epic-TASK-466). The branch's primary task TASK-466 (type=epic) has 4 children and won't be dispatched. This sibling task carries the actual fix work.

Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 03:21
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 03:21
---
Understanding: I need to fix CI test failures on PR #244 (branch epic-TASK-466). I'm already on that branch. Plan: run tests locally to identify failures, diagnose root cause, make minimal fixes, and push.
---

author: oompah
created: 2026-06-09 03:30
---
Discovery: The failing test is tests/test_release_pick_reconciler.py::TestOrchestratorReconcileReleasePicksPass::test_called_by_handle_yolo_review. It asserts that _handle_yolo_review() calls _reconcile_release_picks_pass, but TASK-466.2 moved that call to _do_merged_labels() in the maintenance lane. The test needs to be updated to reflect the new calling path.
---

author: oompah
created: 2026-06-09 03:33
---
Implementation: Updated test_called_by_handle_yolo_review → test_called_by_do_merged_labels in tests/test_release_pick_reconciler.py. TASK-466.2 moved _reconcile_release_picks_pass from _handle_yolo_review to _do_merged_labels (maintenance lane). Renamed and updated test to call _do_merged_labels() directly and verify _reconcile_release_picks_pass is invoked.
---
<!-- COMMENTS:END -->
