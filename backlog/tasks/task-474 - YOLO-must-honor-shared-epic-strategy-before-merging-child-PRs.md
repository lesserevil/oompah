---
id: TASK-474
title: YOLO must honor shared epic strategy before merging child PRs
status: Done
assignee:
  - oompah
created_date: '2026-06-09 16:32'
updated_date: '2026-06-09 16:51'
labels:
  - bug
dependencies: []
priority: high
ordinal: 189000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The oompah project is configured with epic_strategy=shared, but YOLO merged child-task PRs from TASK-472 directly into main before the complete epic landed. Shared epic mode means children commit to the shared epic branch and no per-child PR should merge to main. Add a YOLO pre-merge gate that resolves a review source branch back to its task and blocks merge/enqueue/conflict/ci-fix actions for PRs that violate the project's epic_strategy. Cover shared child PRs targeting main and stacked child PRs targeting the wrong branch.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed YOLO so it honors per-project epic_strategy before acting on reviews. Added a pre-action gate that resolves the review source branch back to a tracker issue and blocks all YOLO actions for shared-mode child PRs and stacked-mode child PRs targeting anything other than the parent epic branch. Covered the incident regression with tests for shared child PRs blocking merge/conflict/CI actions, stacked wrong-target blocking, valid stacked child merges, and shared nested epic branch rollups.
<!-- SECTION:FINAL_SUMMARY:END -->
