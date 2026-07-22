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
updated_at: '2026-07-22T23:28:51.648902Z'
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
<!-- COMMENTS:END -->
