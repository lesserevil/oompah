---
id: TASK-399
title: Fix BacklogMdTracker cost metadata write path
status: To Do
assignee: []
created_date: '2026-06-01 16:07'
labels:
  - bug
dependencies: []
priority: high
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During the 2026-06-01 restart, TASK-388 completed but the log reported: cost_record: failed to write metadata for TASK-388: 'BacklogMdTracker' object has no attribute '_run_bd'. The cost metadata writer still calls a Beads-specific helper on the Backlog tracker path. Update it to use the Backlog.md task API or skip unsupported metadata writes cleanly.
<!-- SECTION:DESCRIPTION:END -->
