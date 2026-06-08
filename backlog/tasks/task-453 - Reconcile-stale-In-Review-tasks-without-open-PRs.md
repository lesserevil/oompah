---
id: TASK-453
title: Reconcile stale In Review tasks without open PRs
status: Done
assignee:
  - oompah
created_date: '2026-06-08 16:16'
updated_date: '2026-06-08 16:23'
labels: []
dependencies: []
priority: high
ordinal: 89000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In Review tasks can remain visible after their review PR is closed or superseded. Add background reconciliation so tasks with no live review PR leave In Review based on merged/closed branch state.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added background reconciliation for stale In Review tasks: open cached/provider reviews are preserved, merged branches/PRs become Merged, closed or missing reviews with commits ahead reopen with a diagnostic comment, and unverifiable branches move to Needs Human. Covered by orchestrator and handler tests; full make test passed.
<!-- SECTION:FINAL_SUMMARY:END -->
