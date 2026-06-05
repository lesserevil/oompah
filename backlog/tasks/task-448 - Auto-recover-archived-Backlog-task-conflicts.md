---
id: TASK-448
title: Auto-recover archived Backlog task conflicts
status: Done
assignee:
  - oompah
created_date: '2026-06-05 15:56'
updated_date: '2026-06-05 16:00'
labels:
  - bug
dependencies: []
priority: high
ordinal: 84000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: oompah quarantines managed repos when conflicted Backlog task files live under backlog/archive/tasks, but the auto-repair scanners only include backlog/tasks and backlog/completed. Include archived Backlog task paths in marker-based repair and unmerged-index recovery so archived task conflicts are handled automatically instead of requiring operator intervention. Add regression tests for archive task conflict recovery.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed. Archived Backlog task files under backlog/archive/tasks are now included in both marker-based conflict repair and unmerged-index recovery. Added regression coverage for detecting and recovering archived task conflicts.
<!-- SECTION:FINAL_SUMMARY:END -->
