---
id: TASK-465.6
title: Preserve Backlog priority when updating task status
status: Open
assignee: []
created_date: '2026-06-08 19:52'
updated_date: '2026-06-08 19:52'
labels:
  - bug
dependencies: []
parent_task_id: TASK-465
priority: high
ordinal: 167000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During live recovery on 2026-06-08, TASK-465.3 lost its priority: 0 field after a status-only recovery/update path marked it Open for re-dispatch. Priority loss changes scheduler behavior because P0 tasks bypass some gates and are sorted first.

Audit BacklogMdTracker.update_issue and any CLI/direct-frontmatter update path used by dispatch, restart recovery, orphan reset, and handoff-label cleanup. Status-only or comment-only updates must preserve existing priority metadata exactly unless the caller explicitly changes priority.

Acceptance criteria:
- Updating only status preserves an existing priority: 0 field.
- Restart recovery preserves priority on undrained tasks.
- Regression tests cover status updates and restart recovery for P0 tasks.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:52
---
Filed from live recovery: TASK-465.3 lost priority: 0 after status-only restart recovery, which can affect scheduler priority and gate bypass behavior.
---

author: oompah
created: 2026-06-09 00:07
---
Duplicate investigation complete: NOT a duplicate. Two close candidates examined: TASK-397 (Preserve custom Backlog frontmatter, Done 2026-06-02) and TASK-425 (Preserve P0 priority distinct from P1, Done 2026-06-02). Neither covers this specific regression. TASK-425 fixed the write path when explicitly setting priority, but the _custom_frontmatter_snapshot() method excluded 'priority' from its snapshot (because it lives in _BACKLOG_CLI_OWNED_FRONTMATTER), so numeric P0 was still dropped on status-only edits. TASK-465.6 is a distinct bug that manifested live on 2026-06-08 after both prior fixes were shipped. The first agent run (run #1, 2026-06-08 20:59) implemented the full fix and 3 regression tests. All 53 tracker tests pass. The task was not marked Done despite being complete — closing now.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Not a duplicate. Fixed BacklogMdTracker._custom_frontmatter_snapshot() to include numeric priority (int) in the pre-CLI snapshot, so _restore_missing_frontmatter() restores priority: 0 after any status-only Backlog CLI edit drops it. This covers all update paths: reopen_issue, close_issue, update_issue(status=...), add_label, remove_label. Three regression tests added (test_update_issue_status_only_preserves_p0_priority, test_reopen_issue_preserves_p0_priority, test_restart_recovery_preserves_p0_priority). All 53 tracker tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
