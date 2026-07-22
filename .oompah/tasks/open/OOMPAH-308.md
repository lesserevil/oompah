---
id: OOMPAH-308
type: task
status: Open
priority: null
title: Fix stale work_branch metadata for native shared-epic children and update to
  epic branch on dispatch
parent: OOMPAH-307
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:52:58.139774Z'
updated_at: '2026-07-22T05:20:52.511466Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Correct stale shared-epic child branch metadata when dispatching to the parent epic branch.
## Context

When a native (oompah_md) child task has pre-existing work_branch/branch_name metadata in its frontmatter (e.g., from a prior erroneous dispatch), the field is preserved in the in-memory Issue object. Even when _create_workspace_for_issue correctly routes the child to the parent epic worktree, issue.work_branch still holds the stale per-task value (e.g., 'OOMPAH-286' instead of 'epic-OOMPAH-285').

This stale branch is used by _branch_for_issue (lines 7680-7695 in orchestrator.py) in downstream code:
- Done→Merged promotion checks if the per-task branch is in merged_branches; if it is, it may mark the child Merged even though the rollup_strategy guard should catch it
- _ensure_review_exists uses the branch to create a review (though this is guarded by parent_epic check)

## Implementation scope

1. In _create_workspace_for_issue (oompah/orchestrator.py ~line 4767), when routing to the parent epic worktree (parent_epic is not None):
   - Clear issue.work_branch and issue.branch_name from the child's in-memory state (or overwrite with the epic branch name)
   - For oompah_md tracker_kind tasks: call tracker.set_metadata_field(child_id, 'oompah.work_branch', epic_branch_name) to persist the correction to the frontmatter
   - For github_issues tracker_kind children: update the work_branch metadata similarly

2. Ensure the epic branch name (from project_store.epic_branch_name(parent_epic.identifier)) is written as work_branch on the child so _branch_for_issue returns the correct value.

## Relevant files
- oompah/orchestrator.py: _create_workspace_for_issue (~line 4719), _branch_for_issue (~line 7680)
- oompah/oompah_md_tracker.py: set_metadata_field (~line 775)

## Tests required
- test_epic_strategy.py: Add test case where a shared-epic child has work_branch='TASK-1.1' (stale per-task branch) in its issue metadata; after _create_workspace_for_issue, confirm issue.work_branch is updated to the epic branch name, not the per-task value
- Test that set_metadata_field is called on the tracker with the corrected epic branch for oompah_md tasks
- Regression: _branch_for_issue returns epic branch (not stale per-task branch) for a shared-epic child after dispatch routing

## Acceptance criteria
- Shared-epic children dispatched via oompah_md have work_branch set to the parent epic branch, not a per-task branch
- _branch_for_issue(child) returns the epic branch name after routing
- Existing stale work_branch in frontmatter is overwritten on dispatch

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes
