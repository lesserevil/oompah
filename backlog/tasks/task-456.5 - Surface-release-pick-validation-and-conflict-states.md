---
id: TASK-456.5
title: Surface release-pick validation and conflict states
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-10 06:08'
labels:
  - task
dependencies:
  - TASK-456.1
parent_task_id: TASK-456
priority: high
ordinal: 107000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Show branch validation errors, waiting-for-source-merge state, open PRs, merged picks, closed PRs, and cherry-pick conflicts clearly in the UI without requiring operators to inspect logs.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 05:51
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 06:06
---
Understanding (Duplicate Investigator): TASK-456.5 is NOT a duplicate. Searched 'release-pick', 'validation', 'conflict', 'cherry-pick UI'. Closest candidates: TASK-456.2 (task detail panel UI), TASK-456.3 (modal), TASK-456.4 (epic matrix) — all cover different scope. TASK-456.5 specifically surfaces validation errors, closed PR states, waiting/conflict states in the UI. A prior agent (2026-06-08 23:05) already implemented the work: added .release-pick-validation-error and .release-pick-pr-closed CSS classes, updated renderReleasePicksSection to show validation errors and PR state-aware links, updated releasePickNextAction with descriptive messages, and added tests/test_dashboard_release_pick_states.py. All changes were included in the merged PR #239 (commit bb3979a).
---

author: oompah
created: 2026-06-10 06:07
---
Verification: All 16 tests in tests/test_dashboard_release_pick_states.py pass. Tests cover: CSS classes (validation-error uses red, pr-closed uses muted/line-through), renderReleasePicksSection (reads is_valid/validation_error, shows (closed) text, distinguishes open vs closed PR, shows ✓ for merged), releasePickNextAction (waiting mentions source merge, conflict mentions resolve/re-pick), status badge colors (conflict=red, merged=green). 341 release-pick module tests pass total. Zero regressions.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implementation complete (delivered in merged PR #239, commit bb3979a). Not a duplicate. dashboard.html updated with: .release-pick-validation-error CSS (red, shown when is_valid=false), .release-pick-pr-closed CSS (line-through/muted), renderReleasePicksSection state-aware PR links (pr_open=active, merged=✓, else=(closed)), validation error banner per entry, releasePickNextAction 'waiting'='Waiting for source to merge' / 'conflict'='Resolve conflict and re-pick'. 16 new tests in test_dashboard_release_pick_states.py, all passing.
<!-- SECTION:FINAL_SUMMARY:END -->
