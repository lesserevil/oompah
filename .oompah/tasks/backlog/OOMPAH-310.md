---
id: OOMPAH-310
type: task
status: Backlog
priority: null
title: Verify and harden epic-merge-triggered Merged promotion for shared-epic children
parent: OOMPAH-307
children:
- OOMPAH-412
- OOMPAH-413
blocked_by:
- OOMPAH-308
- OOMPAH-309
labels:
- focus-complete:duplicate_detector
- focus-complete:epic_planner
assignee: null
created_at: '2026-07-21T16:53:34.544944Z'
updated_at: '2026-07-22T21:34:54.702188Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3af06b99-69a5-44cf-8c29-7e224f7982f1
oompah.task_costs:
  total_input_tokens: 90
  total_output_tokens: 9139
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 90
      output_tokens: 9139
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 33
    output_tokens: 7117
    cost_usd: 0.0
    recorded_at: '2026-07-22T16:18:15.274827+00:00'
  - profile: default
    model: unknown
    input_tokens: 57
    output_tokens: 2022
    cost_usd: 0.0
    recorded_at: '2026-07-22T21:34:53.016501+00:00'
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
author: oompah
created: 2026-07-22 16:18
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate found. OOMPAH-310 is a unique, unimplemented task.

2. Relevant files, commands, evidence, and decisions:
   - OOMPAH-307 epic planner (comment #15) created OOMPAH-310 explicitly to address Gap D.
   - Key code in oompah/orchestrator.py:
     * _mark_epic_merged (~line 10676): marks epic and all children Merged. Contains child loop that skips only MERGED/ARCHIVED children. Needs verification that it correctly gates on epic branch being confirmed merged.
     * _reconcile_merged_epic_children (~line 10522): sweeps existing merged epics and calls _mark_epic_merged for each — entry path driven by _all_merged_epics(). Needs verification that it does not fire prematurely for shared-epic children.
     * _label_merged_epics (also calls _mark_epic_merged via line 5707) — drives promotion from the merged-branches set; should only fire after the epic branch merges to target.
     * _epic_rollup_child_strategy check at line 8282 (Done→Merged guard for one path).
     * Done→Merged promotion path at ~line 8607 that also depends on rollup_strategy being 'shared'.
   - OOMPAH-308 (Done) fixed stale work_branch metadata so children's branch correctly reflects the epic branch — this is a prerequisite for OOMPAH-310.
   - OOMPAH-309 (In Review) hardens _resolve_parent_epic failure paths — also a prerequisite.

3. Remaining work:
   - Read and verify _mark_epic_merged, _reconcile_merged_epic_children, and all Done→Merged promotion paths in orchestrator.py.
   - Confirm each path requires confirmed epic-branch merge (not just Done state on the child) before setting children Merged.
   - Identify any gap where a child could be promoted to Merged before the epic branch merges.
   - If gaps exist: add guards (e.g., verify epic is in MERGED state before promoting children; ensure rollup_strategy is 'shared' check is present on all promotion paths).
   - Write/extend tests in tests/test_epic_strategy.py covering: (a) child NOT promoted to Merged while epic is still open, (b) child IS promoted to Merged only after epic lands, (c) regression for the two promotion paths at ~8282 and ~8607.
   - Run make test to verify.

4. Recommended next focus: feature (backend verification and hardening of epic-merge-triggered Merged promotion in oompah/orchestrator.py).
---
author: oompah
created: 2026-07-22 16:18
---
Agent completed successfully in 211s (7150 tokens)
---
author: oompah
created: 2026-07-22 16:18
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 58, Tool calls: 44
- Tokens: 33 in / 7.1K out [7.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 31s
- Log: OOMPAH-310__20260722T161453Z.jsonl
---
author: oompah
created: 2026-07-22 16:18
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 21:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 21:30
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 21:33
---
Understanding: Acting as Epic Planner for OOMPAH-310. The task is to verify and harden the epic-merge-triggered Merged promotion for shared-epic children so that children are ONLY promoted to Merged after the parent epic branch is confirmed merged to the target branch.

Code audit findings from exploration:
1. _label_merged_epics (line 10421): Correctly gated by _epic_branch_landed_on_target() before calling _mark_epic_merged. Appears sound.
2. _open_epic_main_prs (line 5680): Also gated by _epic_branch_landed_on_target(). Appears sound.
3. _reconcile_merged_epic_children (line 10522): Only fires when epic is already in MERGED state (via _all_merged_epics()). Appears sound.
4. Deferred Done reviews path (line 8545): Has 'if issue.parent_id and rollup_strategy == shared: continue'. Appears sound.
5. label_merged_issues path (line 8935): Has 'if rollup_strategy == shared and not helper_issue: continue'. Appears sound.

Existing test coverage in tests/test_epic_strategy.py:
- TestLabelMergedEpics class: tests _label_merged_epics paths
- test_merged_epic_reconciles_children_still_done: tests _reconcile_merged_epic_children
- test_shared_done_child_with_merged_branch_skips_all_checks: tests deferred Done reviews path

Planning approach: Decompose into (1) a code audit + hardening task and (2) a regression tests task, since the scope covers multiple orchestrator.py functions and a 4034-line test file. The audit must confirm no gaps exist; the test task fills in any coverage gaps.
---
author: oompah
created: 2026-07-22 21:34
---
Focus handoff: epic_planner

1. Outcome: Epic decomposition complete. Two child tasks created under OOMPAH-310.

2. Relevant files, commands, evidence, and decisions:
   - All 3 callers of _mark_epic_merged in oompah/orchestrator.py (lines 5707, 10475, 10545) appear correctly gated by either _epic_branch_landed_on_target() or by requiring the epic to already be in MERGED state.
   - Two additional Merged promotion paths (deferred Done reviews ~line 8545, label_merged_issues ~line 8935) both have rollup_strategy == 'shared' guards.
   - Existing test classes: TestLabelMergedEpics (~line 3533), test_merged_epic_reconciles_children_still_done, test_shared_done_child_with_merged_branch_skips_all_checks.
   - Child tasks: OOMPAH-412 (audit + harden), OOMPAH-413 (regression tests, depends on OOMPAH-412).

3. Remaining work:
   - OOMPAH-412: Feature agent reads all 6 code paths, documents guard status, adds hardening if gaps found.
   - OOMPAH-413: Feature agent fills remaining test coverage gaps and runs make test.

4. Recommended next focus: feature agent on OOMPAH-412 first (OOMPAH-413 depends on it).
---
author: oompah
created: 2026-07-22 21:34
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 41
- Tokens: 57 in / 2.0K out [2.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 33s
- Log: OOMPAH-310__20260722T213024Z.jsonl
---
<!-- COMMENTS:END -->
