---
id: OOMPAH-310
type: task
status: Open
priority: null
title: Verify and harden epic-merge-triggered Merged promotion for shared-epic children
parent: OOMPAH-307
children: []
blocked_by:
- OOMPAH-308
- OOMPAH-309
labels: []
assignee: null
created_at: '2026-07-21T16:53:34.544944Z'
updated_at: '2026-07-21T18:40:47.496871Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

## Context

The epic rollup model requires that shared-epic children are NOT promoted to Merged when their own work completes; they should only reach Merged when the parent epic's PR merges to its target branch. The current code has partial protection:

- _epic_rollup_child_strategy returns 'shared' for children of rollup parents
- Done→Merged promotion checks rollup_strategy at two places (~line 8282 and ~line 8607) and skips when 'shared'
- _open_epic_main_prs promotes the epic to Merged, but children are not explicitly promoted at that point

However, it is not clear that a clear code path exists for: 'epic PR merges to target → all children promoted to Merged'. The epic_rollup_state() function in statuses.py does handle this for the rollup state computation, but the actual per-child status update after epic merge needs verification.

## Implementation scope

1. Trace and document the exact code path that fires after an epic PR is confirmed merged to target_branch (in _open_epic_main_prs / _mark_epic_merged / webhook handler). Identify if and where children are promoted to Merged.

2. If no explicit promotion path exists for children after epic merge: implement _promote_shared_epic_children_to_merged(epic: Issue) that:
   - Fetches all children of the epic
   - Filters to those with status Done (completed on epic branch)
   - Marks them Merged via tracker.update_issue(child.identifier, status=MERGED)
   - Logs the promotion

3. Call _promote_shared_epic_children_to_merged from the epic merge confirmation path (wherever _mark_epic_merged or equivalent is called).

4. Verify that children in Done state for shared epics do NOT get promoted to Merged by the normal Done→Merged polling path (line 8282 guard is working correctly for all failure modes).

## Relevant files
- oompah/orchestrator.py: _open_epic_main_prs (~line 5349), _mark_epic_merged (search for this), Done→Merged promotion (~lines 8280-8330)
- oompah/statuses.py: epic_rollup_state function

## Tests required
- test_epic_strategy.py: After epic PR merges to target, all Done children are promoted to Merged
- Children in Done state for a shared epic are NOT promoted to Merged by the normal Done→Merged tick
- Child in Done state remains Done if epic PR is not yet merged
- Child in Done state is promoted to Merged after epic PR confirms merge

## Acceptance criteria
- Shared-epic children in Done state are promoted to Merged if and only if the parent epic's PR has merged to its target branch
- No child is falsely labeled Merged before the epic delivery is confirmed merged

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

