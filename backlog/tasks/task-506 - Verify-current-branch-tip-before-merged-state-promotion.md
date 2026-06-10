---
id: TASK-506
title: Verify current branch tip before merged-state promotion
status: Done
assignee:
  - oompah
created_date: '2026-06-10 06:53'
updated_date: '2026-06-10 06:55'
labels: []
dependencies: []
priority: high
ordinal: 226000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Oompah can mark a task Merged from stale merged-branch history when a branch name was previously merged but the current remote branch tip has new unmerged commits. This stranded trickle TASK-737: GitHub had an old merged PR for TASK-737, but origin/TASK-737 was not an ancestor of origin/main, so the task was promoted to Merged and its worktree was cleaned before a new PR existed. Add a git ancestry/ahead guard anywhere merged branch history promotes or skips task review handoff, and add regression tests.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed stale merged-branch reconciliation. Oompah now treats forge merged-branch history as a candidate signal and verifies any current managed branch ref against the target branch before marking tasks Merged or skipping deferred Done review handoff. If the branch still exists and is ahead, merged promotion is skipped and stale In Review reconciliation reopens the task instead. Added regressions for merged-label promotion, stale In Review reconciliation, and deferred Done review handoff. Verification: uv run pytest tests/test_orchestrator_merged.py tests/test_epic_strategy.py -q (240 passed).
<!-- SECTION:FINAL_SUMMARY:END -->
