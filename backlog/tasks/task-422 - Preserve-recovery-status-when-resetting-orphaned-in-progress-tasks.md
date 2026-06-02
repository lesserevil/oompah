---
id: TASK-422
title: Preserve recovery status when resetting orphaned in-progress tasks
status: Done
assignee:
  - oompah
created_date: '2026-06-02 19:35'
updated_date: '2026-06-02 19:37'
labels: []
dependencies: []
priority: high
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: restart/orphan cleanup resets every orphaned In Progress task to Open. For label-driven recovery tasks, that loses semantic status. Example: trickle-704 had label ci-fix and an open failing PR; after the service restart killed the CI-fix agent, orphan cleanup reset the task to Open. The YOLO retry path then sees the ci-fix label and treats the fix as already in flight, but the dashboard no longer shows Needs CI Fix and the dispatcher may not start a CI-fix agent. Fix requirements: when _reset_orphaned_in_progress handles an orphaned issue with ci-fix label, reset status to Needs CI Fix; when it has merge-conflict label, reset to Needs Rebase; ordinary orphaned In Progress issues should still reset to Open. Add tests for ci-fix, merge-conflict, and existing Open behavior.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed orphaned In Progress cleanup so recovery-labeled tasks keep their semantic recovery state. Orphaned ci-fix tasks now reset to P0 Needs CI Fix, merge-conflict tasks reset to P0 Needs Rebase, and ordinary tasks still reset to Open. Verified with focused tests and full make test: 4100 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
