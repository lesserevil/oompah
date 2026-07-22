---
id: OOMPAH-412
type: task
status: In Progress
priority: null
title: Audit and harden all shared-epic Merged promotion paths in orchestrator.py
parent: OOMPAH-310
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T21:34:07.971835Z'
updated_at: '2026-07-22T23:30:18.974580Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b0d974b6-310e-47de-90c8-44d65f314e35
---
## Summary

### Goal
Systematically verify every code path in oompah/orchestrator.py that can transition a task to the Merged state and confirm that shared-epic children can ONLY reach Merged after their parent epic's branch is confirmed merged to the target branch. If any gap is found, add the necessary guard.

### Context
OOMPAH-310 was created by the OOMPAH-307 epic planner to address Gap D: the epic-merge-triggered Merged promotion path needs verification and hardening. The duplicate_detector confirmed no existing implementation addresses this.

### Code paths to audit (oompah/orchestrator.py)

1. **_label_merged_epics** (~line 10421): Calls _mark_epic_merged after checking _epic_branch_landed_on_target(). Verify the gate is applied before any child is promoted.

2. **_open_epic_main_prs** (~line 5680): Calls _mark_epic_merged at line 5707 after checking _epic_branch_landed_on_target(). Verify the guard cannot be bypassed.

3. **_reconcile_merged_epic_children** (~line 10522): Sweeps _all_merged_epics() and calls _mark_epic_merged. The epic must already be MERGED. Verify _all_merged_epics() cannot return prematurely-MERGED epics (e.g., when OOMPAH-311 annotations cause premature state changes).

4. **_open_deferred_done_reviews** (~line 8545): Has 'if issue.parent_id and rollup_strategy == shared: continue'. Verify this guard fires BEFORE any Merged promotion.

5. **_label_merged_issues** (~line 8935): Has 'if rollup_strategy == shared and not helper_issue: continue'. Verify this fires before any Merged update_issue call.

6. **_mark_epic_merged** (~line 10676): The core promotion function. Verify it does NOT need its own internal rollup_strategy check (callers are all gated). If any caller path is found un-gated, add a safety check here.

### Hardening
For each gap found: add the appropriate guard (check rollup_strategy == 'shared', verify epic is in MERGED state, or require _epic_branch_landed_on_target to return True).

### Acceptance criteria
- All 6 code paths above are documented with their guard status.
- Zero paths can promote a shared-epic child to Merged while the parent epic branch is unmerged.
- Any hardening code added is committed to oompah/orchestrator.py on the OOMPAH-310 branch.
- Post a comment summarizing findings (path-by-path) and any code changes made.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 23:28
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 23:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 23:28
---
Understanding: I am the Duplicate Investigator for OOMPAH-412. This task asks to audit and harden all shared-epic Merged promotion paths in orchestrator.py, ensuring shared-epic children can only reach Merged state after their parent epic branch is confirmed merged. The description explicitly references OOMPAH-310 and OOMPAH-307. I will now search for related/duplicate tasks before any implementation begins.
---
author: oompah
created: 2026-07-22 23:30
---
Discovery: Duplicate screening found NO duplicate for OOMPAH-412.

Search scope: All .oompah/tasks/ folders (archived, merged, done, open, backlog), docs/, plans/, README.md, WORKFLOW.md.

Keywords searched: shared-epic, mark_epic_merged, label_merged_epics, reconcile_merged_epic, Merged promotion, harden.*promotion, audit.*orchestrator, shared_epic, promotion paths.

Zero keyword matches across the task filesystem.

Candidates reviewed by ID and REJECTED:
- OOMPAH-310 (Open, parent): 'Verify and harden epic-merge-triggered Merged promotion for shared-epic children' — this is the PARENT of OOMPAH-412, not a duplicate. OOMPAH-412 was explicitly created by the OOMPAH-310 Epic Planner (comment #12) as a decomposed child for the code audit + hardening sub-scope.
- OOMPAH-309 (Merged): 'Harden shared-epic protection when _resolve_parent_epic fails' — different scope: covers failure-path hardening when parent lookup throws; resolved and merged.
- OOMPAH-311 (referenced as Done): 'Diagnose and surface remediation for existing independently-merged children' — different scope: covers detection and annotation of already-merged child branches, not Merged promotion gating.
- OOMPAH-308 (Done): 'Fix stale work_branch metadata when child routes to shared epic worktree' — different scope: fixes metadata corruption at dispatch time, not the Merged promotion paths.
- OOMPAH-312 (Open): 'UI/dashboard status display' — different scope: display labels.
- OOMPAH-313: Regression tests for OOMPAH-285/286 fixture — different scope: routing lifecycle tests, not the 6 promotion-path audit.
- OOMPAH-413 (Open, sibling): Regression tests depending on OOMPAH-412 audit results — this is a sibling test task, not a duplicate of the audit/hardening work.

Conclusion: OOMPAH-412 is NOT a duplicate. It is a unique, properly decomposed child task of OOMPAH-310 with a specific scope: audit the 6 Merged promotion code paths in orchestrator.py and add hardening guards where gaps are found.
---
<!-- COMMENTS:END -->
