---
id: TASK-399
title: Fix BacklogMdTracker cost metadata write path
status: Done
assignee: []
created_date: '2026-06-01 16:07'
updated_date: '2026-06-03 02:04'
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
Merge conflict resolved and PR merged. Rebased TASK-399 branch onto origin/main and resolved 5 conflicted files. Key resolution: main had already fixed the bug with BacklogMdTracker.get_metadata()/set_metadata_field() protocol; TASK-399 used get_cost_metadata()/set_cost_metadata(). Resolved by adopting main's API (BeadsTracker was deleted in main). Also preserved TASK-397/TASK-408 frontmatter preservation tests from main while adapting the integration test to use the new API. The fix was force-pushed and merged as PR #208.
<!-- SECTION:FINAL_SUMMARY:END -->
