---
id: TASK-452
title: Preserve Done worktrees during background cleanup
status: Done
assignee:
  - oompah
created_date: '2026-06-08 01:01'
updated_date: '2026-06-08 01:06'
labels:
  - bug
dependencies: []
priority: high
ordinal: 88000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The scheduled managed worktree cleanup currently removes worktrees for every tracker terminal state, including Done. Done worktrees may still be needed when there are conflicts or similar follow-up work. Narrow the cleanup to only remove Merged and Archived worktrees, and add regression coverage proving Done is preserved.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Narrowed scheduled/startup worktree cleanup to only remove Merged and Archived tasks. Done worktrees are now preserved even if a tracker returns them from cleanup queries. Added regression coverage for managed project cleanup, error continuation, and legacy workspace preservation. Verification: tests/test_orchestrator_handlers.py passed (143 passed); make test passed (4568 passed, 15 warnings).
<!-- SECTION:FINAL_SUMMARY:END -->
