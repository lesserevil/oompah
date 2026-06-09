---
id: TASK-475
title: Merged-label reconciliation must honor per-project epic strategy
status: Done
assignee:
  - oompah
created_date: '2026-06-09 17:14'
updated_date: '2026-06-09 17:32'
labels: []
dependencies: []
priority: high
ordinal: 203000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Merged branch reconciliation currently treats any merged branch matching a task identifier as proof that the task is Merged. For projects configured with epic_strategy=shared or epic_strategy=stacked, child tasks under an epic must not be independently marked Merged from their child branch; the epic rollup merge is the source of truth. Update reconciliation so the per-project epic strategy drives this behavior, and add regression tests.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed merged-label and stale In Review reconciliation so per-project epic_strategy controls child merge status. Flat projects still mark matching merged branches as Merged. Shared epic children no longer get promoted from child-branch PR artifacts and wait for the epic rollup merge. Stacked epic children advance to Done when their child PR merges into the epic branch; Merged remains owned by the epic rollup. Added regression tests and verified with focused suites plus full make test.
<!-- SECTION:FINAL_SUMMARY:END -->
