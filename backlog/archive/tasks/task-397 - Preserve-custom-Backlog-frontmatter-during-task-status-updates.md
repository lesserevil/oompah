---
id: TASK-397
title: Preserve custom Backlog frontmatter during task status updates
status: Done
assignee: []
created_date: '2026-06-01 16:07'
updated_date: '2026-06-02 01:24'
labels:
  - bug
dependencies: []
priority: high
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During stale-task cleanup on 2026-06-01, Backlog.md task edits reserialized task frontmatter and dropped historical fields such as type, parent, and beads.*. Oompah should preserve project-specific metadata when it marks Backlog tasks In Progress or Done, or add a repair/preservation layer around CLI edits. Repro: edit TASK-388/TASK-389 status via the current BacklogMdTracker path and inspect the diff.

Implementation guidance (merged from duplicate TASK-408):
- Audit BacklogTracker methods that call `backlog task edit` for mutations (update_issue, close_issue, reopen_issue, add_comment, add_label, remove_label, add_dependency).
- Either preserve and reapply unknown frontmatter after CLI edits, or use a structured local markdown/frontmatter update path for mutations where Backlog CLI cannot preserve metadata.
- Add regression coverage with a task containing nested custom frontmatter.
- Verify normal Backlog fields still update exactly once and comments/final summaries still work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Updating a task status through oompah preserves unknown top-level frontmatter fields and nested custom objects such as beads.
- [ ] #2 Dispatching a task to In Progress preserves migrated beads metadata in the task file.
- [ ] #3 Tests cover status updates and at least one other mutation path that uses BacklogTracker task edits.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented in TASK-408 branch: added _KNOWN_BACKLOG_FIELDS constant and _run_backlog_for_task() wrapper in oompah/tracker.py; all 7 mutation methods now preserve unknown frontmatter. 4 regression tests added.
<!-- SECTION:FINAL_SUMMARY:END -->
