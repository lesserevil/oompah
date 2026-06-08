---
id: TASK-451
title: Periodically clean terminal managed worktrees in the background
status: Done
assignee:
  - oompah
created_date: '2026-06-08 00:14'
updated_date: '2026-06-08 00:21'
labels:
  - task
dependencies: []
priority: high
ordinal: 87000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Oompah currently removes managed project worktrees for terminal Backlog tasks only at orchestrator startup and when a running task is moved to a terminal status through the UI. Add a scheduled/background cleanup pass so worktrees for tasks in terminal states (Done, Merged, Archived) are cleaned while the service keeps running, including after merge queue merges mark tasks Merged. Reuse the existing ProjectStore.remove_worktree path and add tests that the periodic tick invokes cleanup without disrupting active/non-terminal worktrees.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added a scheduled background cleanup pass for managed project worktrees. Terminal cleanup is now reusable, startup cleanup calls it, and the periodic repo self-heal/full-sync path invokes it for managed projects so Done/Merged/Archived worktrees are removed while the service is running. Added orchestrator regression tests for terminal cleanup, error continuation, full-sync invocation, cadence skipping, and cleanup after repo-heal failure. Verification: targeted tests/test_orchestrator_handlers.py passed (142 passed); make test passed (4549 passed, 18 warnings).
<!-- SECTION:FINAL_SUMMARY:END -->
