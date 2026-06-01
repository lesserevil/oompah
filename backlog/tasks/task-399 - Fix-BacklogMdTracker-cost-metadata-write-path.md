---
id: TASK-399
title: Fix BacklogMdTracker cost metadata write path
status: Backlog
assignee: []
created_date: 2026-06-01 16:07
updated_date: 2026-06-01 20:50
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding: Bug is in orchestrator.py _write_task_cost_record (~line 6500). Calls tracker._run_bd() directly (BeadsTracker-only). When BacklogMdTracker is used, raises AttributeError. Fix: add get_cost_metadata/set_cost_metadata to both tracker classes, update _write_task_cost_record to use them.
<!-- SECTION:NOTES:END -->
