---
id: TASK-455.6
title: Reconcile release-pick PR outcomes
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-09 01:38'
labels:
  - task
dependencies:
  - TASK-455.4
parent_task_id: TASK-455
priority: high
ordinal: 101000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Track release-pick child PRs after creation. When a target PR merges, mark the child task Merged and source target status merged; when closed unmerged, reopen or escalate with an actionable comment.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 01:33
---
Implementation: Added _check_pr_outcome() function to oompah/release_pick_reconciler.py (TASK-455.6). The function queries the SCM provider for each pr_open/cherry_picking entry: (1) merged PR → child marked Merged, child backport_of updated to merged, entry advances to merged; (2) closed unmerged → actionable comment posted on source task, child backport_of updated to needs_human, entry escalates to needs_human; (3) open PR → no change; (4) PR not found or SCM error → entry unchanged, error logged. Integrated as Case 2 in _reconcile_entries() before the existing task_created+cherry-pick case. Updated module docstring, NEEDS_HUMAN import, and TYPE_CHECKING block. 34 new tests added (TestCheckPrOutcome: 20 tests, TestReconcilePrOutcomeIntegration: 10 tests).
---

author: oompah
created: 2026-06-09 01:38
---
Verification: 97 tests pass in test_release_pick_reconciler.py (34 new for TASK-455.6: TestCheckPrOutcome x20, TestReconcilePrOutcomeIntegration x10). 247 tests pass across release_pick_reconciler, cherry_pick_pr_creator, and release_pick_schema modules combined. No regressions. Branch pushed to origin/epic-TASK-455.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented _check_pr_outcome() in oompah/release_pick_reconciler.py to reconcile release-pick PR outcomes (TASK-455.6). When a pr_open/cherry_picking entry's PR is merged: child task marked Merged, child backport_of updated to merged, source backports entry advances to merged. When PR closed unmerged: actionable comment posted on source task, child backport_of updated to needs_human, entry escalates to needs_human. Open PRs unchanged (re-checked next tick). SCM errors logged but non-fatal. 34 new tests (97 total). All 247 tests across release-pick modules pass.
<!-- SECTION:FINAL_SUMMARY:END -->
