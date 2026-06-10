---
id: TASK-500
title: Shared-mode review handoff must not strand non-epic parented tasks
status: Done
assignee:
  - oompah
created_date: '2026-06-10 02:12'
updated_date: '2026-06-10 02:12'
labels: []
dependencies: []
priority: high
ordinal: 218000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In projects with epic_strategy=shared, _ensure_review_exists skipped per-child PR creation for any task with parent_id, even when the parent did not resolve as an epic. Those tasks use per-task worktrees and pushed task branches, so skipping review handoff strands completed work with no PR. Only real epic children should skip per-child PR creation.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 02:12
---
Fix in progress: update shared-mode review handoff so only children of an actual epic skip per-child PR creation; non-epic parented tasks continue through normal review handoff.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed shared-mode review handoff so tasks with a non-epic parent no longer skip PR creation. True shared-epic children still wait for the epic rollup PR. Added regression coverage in tests/test_epic_strategy.py. Verification: .venv/bin/python -m pytest tests/test_epic_strategy.py::TestEnsureReviewExistsRespectsEpicStrategy tests/test_epic_strategy.py::TestDeferredDoneReviews -q passed (16 tests).
<!-- SECTION:FINAL_SUMMARY:END -->
