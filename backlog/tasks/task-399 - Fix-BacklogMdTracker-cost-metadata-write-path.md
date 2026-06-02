---
id: TASK-399
title: Fix BacklogMdTracker cost metadata write path
status: Done
assignee: []
created_date: 2026-06-01 16:07
updated_date: 2026-06-02 02:50
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
Fix implemented in commit 6c2369e. Added get_cost_metadata/set_cost_metadata protocol to both BeadsTracker and BacklogMdTracker. Updated _write_task_cost_record in orchestrator.py to use the uniform protocol instead of calling _run_bd() directly. Trackers lacking the protocol are skipped at DEBUG level. All 3833 tests pass. Duplicate investigation (2026-06-02): searched 'BacklogMdTracker', 'cost metadata', '_run_bd', 'cost_record' — no duplicates found, TASK-399 is the original issue. All 39 related tests verified passing on re-check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Duplicate investigation: no duplicates found. Original fix (commit 6c2369e) added get_cost_metadata/set_cost_metadata protocol to BeadsTracker and BacklogMdTracker; updated _write_task_cost_record to use this uniform interface instead of calling _run_bd() directly. Trackers without the protocol are skipped cleanly at DEBUG level. All 39 related tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
