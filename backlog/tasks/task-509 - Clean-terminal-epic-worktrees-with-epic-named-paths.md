---
id: TASK-509
title: Clean terminal epic worktrees with epic-named paths
status: Done
assignee:
  - oompah
created_date: '2026-06-10 10:43'
updated_date: '2026-06-10 10:44'
labels:
  - bug
dependencies: []
priority: high
ordinal: 235000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Terminal worktree cleanup removes Merged/Archived task worktrees, but shared epic worktrees live under epic-<task-id>. Route terminal epic issues through ProjectStore.remove_epic_worktree so merged or archived epic rollup worktrees are actually removed while preserving Done worktrees.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed terminal worktree cleanup so Merged/Archived epic rollups use the epic-named worktree removal path. Added regression coverage proving merged epic worktrees are removed while Done epic worktrees are preserved. Verification: uv run pytest tests/test_orchestrator_handlers.py::TestTerminalWorktreeCleanup -q; uv run pytest tests/test_projects.py tests/test_project_locks.py -q; git diff --check; python -m compileall -q oompah/orchestrator.py.
<!-- SECTION:FINAL_SUMMARY:END -->
