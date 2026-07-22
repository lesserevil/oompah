---
id: OOMPAH-310
type: task
status: In Progress
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
updated_at: '2026-07-22T16:17:38.548442Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5a9931fd-3a15-4f13-88c0-2b9b10e0d5b7
---
## Summary

Verify shared-epic child promotion to Merged occurs only after the epic merge.
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 16:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 16:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 16:15
---
Understanding: Acting as Duplicate Investigator for OOMPAH-310. This task is about verifying that shared-epic children are only promoted to Merged state after the epic itself merges (epic-merge-triggered promotion). I will search the task tracker and codebase for similar issues before any implementation work begins.
---
author: oompah
created: 2026-07-22 16:17
---
Discovery: Duplicate screening found NO duplicate for OOMPAH-310.

Search scope: all .oompah/tasks/ folders (archived, merged, done, open, in-progress, backlog), plans/, docs/, README.md, WORKFLOW.md, and the oompah/ source tree.

Keywords searched: shared-epic, shared_epic, epic_merge, epic merge, promote Merged, Merged promotion, promote.*merged, mark_epic_merged, premature Merged, children promotion, epic-merge-triggered.

All candidate tasks reviewed and REJECTED as duplicates:
- OOMPAH-308 (Done): Fix stale work_branch metadata when child routes to shared epic worktree — different; covers routing-time metadata correction, not the Merged promotion lifecycle.
- OOMPAH-309 (In Review): Harden shared-epic protection when _resolve_parent_epic fails — different; covers runtime failure-path hardening for dispatch protection, not the Merged promotion trigger.
- OOMPAH-311 (Done): Diagnose and surface remediation for existing independently-merged child branches — different; covers detection and annotation of already-merged children, not gating Merged promotion on the epic merge event.
- OOMPAH-312 (Open): UI/dashboard status display — different; covers display labels, not Merged promotion logic.
- OOMPAH-165 (Archived): Fix shared epic landed detection before main merge — covers a premature landed detection path; was archived; different fix path from OOMPAH-310.
- OOMPAH-219 (Archived): SharedAbsorptionEvidence — covers commit-absorption races; different topic.

OOMPAH-310 was explicitly created by the OOMPAH-307 epic planner (see OOMPAH-307 comment #15) to address Gap D: the epic-merge-triggered Merged promotion path in orchestrator.py needs verification and hardening. The epic planner noted _epic_rollup_child_strategy at line 8282 guards one path but a second path at ~line 8607 also depends on rollup_strategy being 'shared'. This is a distinct, unique, unimplemented task.

Conclusion: OOMPAH-310 is NOT a duplicate. It needs a feature agent to verify and harden _mark_epic_merged and _reconcile_merged_epic_children so shared-epic children are promoted to Merged ONLY when the parent epic branch is confirmed merged, with proper guards where rollup_strategy or parent_id checks could fail.
---
<!-- COMMENTS:END -->
