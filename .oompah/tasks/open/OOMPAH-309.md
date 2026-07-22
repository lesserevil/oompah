---
id: OOMPAH-309
type: task
status: Open
priority: null
title: Harden shared-epic protection when _resolve_parent_epic fails for a child with
  parent_id set
parent: OOMPAH-307
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:53:17.046767Z'
updated_at: '2026-07-22T05:20:53.458361Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Keep shared-epic protections active when resolving a child parent epic fails.
## Context

The shared-epic protection (no per-task worktree, no per-child PR, no Merged promotion) relies on _resolve_parent_epic(issue) returning a non-None parent Issue. This function calls tracker.fetch_issue_detail(parent_id) and returns None on any error:

- Tracker errors (state branch checkout failure, file not found, decode error)
- Parent task not found in the tracker
- Network/IO errors

When _resolve_parent_epic returns None for a child that HAS a non-empty parent_id, the child falls through to:
1. Per-task worktree creation (line 4808, orchestrator.py)
2. Per-child PR creation (no shared-mode skip in _ensure_review_exists when parent_epic is None)
3. Done→Merged promotion (rollup_strategy is None → skip guard doesn't apply)

This is a latent race condition / transient failure that can cause the OOMPAH-286/PR #466 bug pattern to reappear.

## Implementation scope

1. In _resolve_parent_epic (oompah/orchestrator.py ~line 4651): when fetch_issue_detail raises an exception or returns None but parent_id is non-empty, log a warning and consider returning a sentinel/stub parent rather than None. Alternatively, add a secondary lookup (e.g., check if an epic worktree already exists for parent_id as a proxy signal).

2. In _create_workspace_for_issue: if parent_id is non-empty but _resolve_parent_epic returned None, do NOT fall through to per-task worktree. Instead:
   - Try routing to the epic worktree using the parent_id directly (idempotent call to create_epic_worktree with the parent_id)
   - OR requeue the task (raise a retriable exception) so the next tick retries with a fresh tracker lookup

3. In Done→Merged promotion path (~line 8282): if issue.parent_id is non-empty and rollup_strategy is None (resolution failed), do NOT mark Merged. Log a warning and skip (same as 'shared' behavior).

4. In _ensure_review_exists: if parent_id is non-empty but parent_epic resolution failed, skip per-child PR creation (same as parent_epic not None).

## Relevant files
- oompah/orchestrator.py: _resolve_parent_epic (~line 4651), _create_workspace_for_issue (~line 4719), _ensure_review_exists (~line 7803), Done→Merged promotion (~lines 8280-8330, 8595-8625)

## Tests required
- test_epic_strategy.py: Simulate _resolve_parent_epic raising a tracker error for a child with parent_id; verify _create_workspace_for_issue falls back to epic worktree or requeues (not per-task worktree)
- Verify _ensure_review_exists skips per-child PR when parent_id is set but fetch fails
- Verify Done→Merged promotion does NOT mark child Merged when parent_id is set but rollup_strategy is None

## Acceptance criteria
- A transient tracker error during parent_id resolution does not result in a per-child branch, per-child PR, or premature Merged status
- All checks that gate on rollup_strategy == 'shared' are equally applied when parent_id is set but strategy is undetermined

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes
