---
id: TASK-508
title: Enforce epic-owned implementation work for epic-rollup projects
status: Done
assignee:
  - oompah
created_date: '2026-06-10 07:23'
updated_date: '2026-06-10 07:27'
labels:
  - bug
dependencies: []
priority: high
ordinal: 229000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Projects that are configured to land work as epic rollups need an explicit guard so ordinary implementation tasks cannot be dispatched or YOLO-merged as standalone task PRs unless the project allows standalone task PRs. Today epic_strategy=shared only changes behavior after a task has parent_id metadata; top-level tasks still create per-task PRs into main, which let trickle produce TASK-headed PRs despite the operator expecting one PR per epic.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added require_epic_for_tasks as an explicit per-project guard for epic-rollup projects. The project model/store/API persist and validate the boolean flag. Dispatch now rejects top-level non-epic tasks with missing_parent_epic when the flag is enabled; review handoff moves such tasks to Needs Human instead of creating a standalone PR; YOLO gate-blocks already-open standalone task PRs so they cannot merge. Added regression coverage for model round-trip, ProjectStore/API validation, dispatch, review handoff, and YOLO gating.
<!-- SECTION:FINAL_SUMMARY:END -->
