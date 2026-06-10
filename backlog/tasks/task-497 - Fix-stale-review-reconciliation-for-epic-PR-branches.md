---
id: TASK-497
title: Fix stale review reconciliation for epic PR branches
status: Done
assignee:
  - oompah
created_date: '2026-06-10 00:08'
updated_date: '2026-06-10 00:10'
labels: []
dependencies: []
priority: high
ordinal: 213000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stale In Review reconciliation currently falls back to the epic task identifier (for example TASK-459) when checking review/branch state for shared or stacked epic rollup PRs. Epic rollup PRs use epic-<id> branches, so reconciliation can miss an open clean PR, count origin/<task-id>, and incorrectly mark the epic Needs Human. Resolve the effective branch for epic tasks using the project's epic branch naming before checking cached reviews, provider state, merged branches, or commit counts.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed stale In Review reconciliation so stacked/shared epic tasks use the epic rollup branch (for example epic-TASK-459) when matching cached/open reviews and counting branch commits. Added regression coverage for cached and provider-backed open epic PRs.
<!-- SECTION:FINAL_SUMMARY:END -->
