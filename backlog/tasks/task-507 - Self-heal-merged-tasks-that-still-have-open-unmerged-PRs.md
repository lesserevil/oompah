---
id: TASK-507
title: Self-heal merged tasks that still have open unmerged PRs
status: Done
assignee:
  - oompah
created_date: '2026-06-10 07:08'
updated_date: '2026-06-10 07:13'
labels: []
dependencies: []
priority: high
ordinal: 228000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: a managed task can remain in Merged even when GitHub still has an open PR for that task branch and the branch tip is not contained in the target branch. This hides the review from oompah/UI and prevents YOLO from managing it. Add reconciliation that demotes such false terminal state back to In Review or the active conflict status based on the open review.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added merged-label reconciliation self-heal for tasks falsely left Merged while an open PR still exists and the branch is ahead of its target. The repair uses the existing open-review cache, verifies the branch tip against the target, and restores the task to In Review, Needs Rebase, or Needs CI Fix. Added Backlog and GitHub work_branch regression coverage.
<!-- SECTION:FINAL_SUMMARY:END -->
