---
id: TASK-408
title: Preserve custom task frontmatter when updating Backlog tasks
status: Done
assignee: []
created_date: '2026-06-01 23:55'
updated_date: '2026-06-03 01:30'
labels:
  - bug
dependencies: []
priority: high
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Observed while moving TASK-389 through the dashboard/API after fixing status config serialization. The Backlog CLI successfully changed the status, but rewrote the task frontmatter and dropped custom historical fields such as `type` and `beads`. Oompah relies on these migrated fields for historical references and should not silently delete unknown frontmatter when it changes status, assignee, comments, or final summaries.

Reproduction:
1. Use a task file that contains custom frontmatter keys like `type` and nested `beads`.
2. Move it from Open to In Progress through oompah dispatch or update it through the issue API.
3. Inspect the task file diff. The status changes, but unknown metadata is removed because the Backlog CLI rewrites the YAML frontmatter.

Implementation guidance:
- Audit BacklogTracker methods that call `backlog task edit` for mutations.
- Either preserve and reapply unknown frontmatter after CLI edits, or use a structured local markdown/frontmatter update path for mutations where Backlog CLI cannot preserve metadata.
- Add regression coverage with a task containing nested custom frontmatter.
- Verify normal Backlog fields still update exactly once and comments/final summaries still work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Updating a task status through oompah preserves unknown top-level frontmatter fields and nested custom objects such as beads.
- [x] #2 Dispatching a task to In Progress preserves migrated beads metadata in the task file.
- [x] #3 Tests cover status updates and at least one other mutation path that uses BacklogTracker task edits.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Resolved merge conflict by rebasing TASK-408 branch onto main. The branch's e2286a6 commit (_run_backlog_for_task approach) conflicted with main's equivalent implementation (_run_backlog_task_edit + task locks). Resolution: kept main's more complete implementation (thread-safe task locks, direct markdown comment writing, more field handling in update_issue, mark_needs_human method). All 25 test_backlog_tracker tests pass after rebase. Force-pushed TASK-408 branch with clean history.

Core implementation: _BACKLOG_CLI_OWNED_FRONTMATTER constant + _run_backlog_task_edit() wrapper in oompah/tracker.py. All 7 mutation methods (update_issue, close_issue, reopen_issue, add_comment, add_label, remove_label, add_dependency) snapshot and reapply unknown frontmatter around each backlog CLI call. 4 regression tests added; 25/25 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 01:05

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 01:30

Merge conflict resolved: rebased TASK-408 onto main. Conflict was between branch's _run_backlog_for_task() and main's equivalent _run_backlog_task_edit() with task locks. Kept main's more complete implementation. 25/25 tests pass. Force-pushed successfully.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
