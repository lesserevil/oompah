---
id: TASK-408
title: Preserve custom task frontmatter when updating Backlog tasks
status: Done
assignee: []
created_date: '2026-06-01 23:55'
updated_date: '2026-06-02 03:26'
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
- [ ] #1 Updating a task status through oompah preserves unknown top-level frontmatter fields and nested custom objects such as beads.
- [ ] #2 Dispatching a task to In Progress preserves migrated beads metadata in the task file.
- [ ] #3 Tests cover status updates and at least one other mutation path that uses BacklogTracker task edits.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
[oompah] Continuation run (attempt #1): Implementation verified present from previous runs. _KNOWN_BACKLOG_FIELDS and _run_backlog_for_task() wrapper in oompah/tracker.py preserve custom frontmatter across all 7 mutation methods. 13/13 tracker tests pass. TASK-397 is the canonical issue; TASK-408 is the implementation branch. Closing as Done.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implementation complete: Added _KNOWN_BACKLOG_FIELDS constant and _run_backlog_for_task() wrapper in oompah/tracker.py. All 7 mutation methods (update_issue, close_issue, reopen_issue, add_comment, add_label, remove_label, add_dependency) now snapshot custom frontmatter before CLI edits and re-inject any dropped keys afterwards. 13 regression tests pass including 4 dedicated frontmatter-preservation tests (test_update_issue_preserves_custom_frontmatter, test_close_issue_preserves_custom_frontmatter, test_add_label_preserves_custom_frontmatter, and test_add_comment_preserves_nested_frontmatter). TASK-397 is the canonical issue; TASK-408 is the implementation branch.
<!-- SECTION:FINAL_SUMMARY:END -->
