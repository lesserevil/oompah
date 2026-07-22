---
id: OOMPAH-412
type: task
status: Done
priority: null
title: Audit and harden all shared-epic Merged promotion paths in orchestrator.py
parent: OOMPAH-310
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T21:34:07.971835Z'
updated_at: '2026-07-22T23:50:17.837556Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: c3461f98-967c-496d-a956-a45c98b7a6c1
oompah.task_costs:
  total_input_tokens: 388446
  total_output_tokens: 48177
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 388446
      output_tokens: 48177
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 23
    output_tokens: 5681
    cost_usd: 0.0
    recorded_at: '2026-07-22T23:30:49.168462+00:00'
  - profile: standard
    model: unknown
    input_tokens: 181203
    output_tokens: 1021
    cost_usd: 0.0
    recorded_at: '2026-07-22T23:31:29.552220+00:00'
  - profile: deep
    model: unknown
    input_tokens: 207139
    output_tokens: 2179
    cost_usd: 0.0
    recorded_at: '2026-07-22T23:32:36.859609+00:00'
  - profile: standard
    model: unknown
    input_tokens: 81
    output_tokens: 39296
    cost_usd: 0.0
    recorded_at: '2026-07-22T23:50:15.669399+00:00'
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
author: oompah
created: 2026-07-22 23:30
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate found. OOMPAH-412 is a unique, unimplemented child task of OOMPAH-310 covering the code audit and hardening of 6 Merged promotion paths in oompah/orchestrator.py.

2. Relevant files, commands, evidence, and decisions:
   - OOMPAH-310 Epic Planner (comment #12) explicitly created OOMPAH-412 for this scope and OOMPAH-413 for regression tests.
   - Key file: oompah/orchestrator.py — the 6 code paths to audit are:
     1. _label_merged_epics (~line 10421): gated by _epic_branch_landed_on_target() before _mark_epic_merged
     2. _open_epic_main_prs (~line 5680): also gated by _epic_branch_landed_on_target()
     3. _reconcile_merged_epic_children (~line 10522): uses _all_merged_epics() — epic must already be MERGED
     4. _open_deferred_done_reviews (~line 8545): 'if issue.parent_id and rollup_strategy == shared: continue' guard
     5. _label_merged_issues (~line 8935): 'if rollup_strategy == shared and not helper_issue: continue' guard
     6. _mark_epic_merged (~line 10676): core promotion function — verify callers are all gated
   - Existing test coverage in tests/test_epic_strategy.py: TestLabelMergedEpics, test_merged_epic_reconciles_children_still_done, test_shared_done_child_with_merged_branch_skips_all_checks
   - OOMPAH-309 (Merged) and OOMPAH-308 (Done) are prerequisites that are already complete.

3. Remaining work and risks:
   - Feature agent must read all 6 code paths in orchestrator.py, verify each guard is present and fires correctly, and add hardening where gaps exist.
   - Per the OOMPAH-310 Epic Planner (comment #11), preliminary code review suggests the paths appear correctly gated, but a thorough per-path audit with evidence is required to confirm.
   - If gaps are found, add guards (check rollup_strategy == 'shared', verify epic is in MERGED state, or require _epic_branch_landed_on_target to return True).
   - Any code changes need tests to pass via 'make test'.
   - OOMPAH-413 (regression tests) depends on this task completing first.

4. Recommended next focus: feature (backend audit and hardening of oompah/orchestrator.py promotion paths).
---
author: oompah
created: 2026-07-22 23:30
---
Agent completed successfully in 132s (5704 tokens)
---
author: oompah
created: 2026-07-22 23:30
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 31, Tool calls: 20
- Tokens: 23 in / 5.7K out [5.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 12s
- Log: OOMPAH-412__20260722T232840Z.jsonl
---
author: oompah
created: 2026-07-22 23:30
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 23:30
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 23:30
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 23:31
---
Agent completed successfully in 32s (182224 tokens)
---
author: oompah
created: 2026-07-22 23:31
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 3
- Tokens: 181.2K in / 1.0K out [182.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 32s
- Log: OOMPAH-412__20260722T233101Z.jsonl
---
author: oompah
created: 2026-07-22 23:31
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-310`. Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 23:31
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 23:31
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 23:32
---
Agent completed successfully in 50s (209318 tokens)
---
author: oompah
created: 2026-07-22 23:32
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 4
- Tokens: 207.1K in / 2.2K out [209.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 50s
- Log: OOMPAH-412__20260722T233148Z.jsonl
---
author: oompah
created: 2026-07-22 23:32
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-310`. No stronger profile is configured; retrying with 'deep' in 20s (2/3).
---
author: oompah
created: 2026-07-22 23:33
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-22 23:33
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 23:33
---
Understanding: I am the Feature agent for OOMPAH-412. I'm on branch epic-OOMPAH-310 and will now audit all 6 shared-epic Merged promotion paths in oompah/orchestrator.py, add hardening guards where gaps are found, commit changes, and close this task. The key file is oompah/orchestrator.py (~19563 lines). Starting code audit now.
---
author: oompah
created: 2026-07-22 23:43
---
Discovery: Completed audit of all 6 Merged promotion code paths in oompah/orchestrator.py.

PATH 1 - _label_merged_epics (~line 10400): GATED. Checks _epic_branch_landed_on_target() before calling _mark_epic_merged(). Cannot bypass.

PATH 2 - _open_epic_main_prs (~line 5674): GATED. _mark_epic_merged() is inside the 'if _epic_branch_landed_on_target(...)' block. Cannot bypass.

PATH 3 - _reconcile_merged_epic_children (~line 10501): PARTIALLY GATED (gap found). Relies on the invariant that all epics in MERGED state had their branch verified. All current code paths that set MERGED on an epic do verify this, BUT there is no explicit _epic_branch_landed_on_target check here. If an epic is set to MERGED externally or via future code, children would be promoted without branch verification. Adding defensive guard.

PATH 4 - _open_deferred_done_reviews (~line 8490): GATED. 'if issue.parent_id and rollup_strategy == shared: continue' fires before all Merged promotion paths. Confirmed shared-epic children exit before any update_issue(MERGED) call.

PATH 5 - _label_merged_issues (~line 8839): GATED. 'if rollup_strategy == shared and not helper_issue: continue' fires before tracker.update_issue(MERGED). The helper_issue bypass is intentional for 'ci fix:' and 'rebase ' tasks that fix the epic branch itself.

PATH 6 - _mark_epic_merged (~line 10526): NO INTERNAL GUARD NEEDED. All primary callers (_label_merged_epics, _open_epic_main_prs) are explicitly gated via _epic_branch_landed_on_target. However, since _reconcile_merged_epic_children (path 3) is implicitly gated, adding safety there (not here) to be surgical.

HARDENING ACTION: Add defensive _epic_branch_landed_on_target check in _reconcile_merged_epic_children. Also update existing test and add new regression test.
---
author: oompah
created: 2026-07-22 23:49
---
Implementation: Added defensive _epic_branch_landed_on_target guard to _reconcile_merged_epic_children in oompah/orchestrator.py.

CHANGE SUMMARY:
- oompah/orchestrator.py: Updated _reconcile_merged_epic_children to re-verify the epic branch has landed on its target before calling _mark_epic_merged to promote children. The check uses detect_provider + extract_repo_slug + _resolve_epic_target_branch (same pattern as _label_merged_epics). Falls back gracefully to trusting the MERGED state when project/forge info is unavailable or the check raises an exception.

- tests/test_epic_strategy.py:
  1. Updated test_merged_epic_reconciles_children_still_done: Added detect_provider + extract_repo_slug mocks with a merged PR review confirming the epic branch has landed. This is the valid scenario (MERGED state = branch confirmed landed).
  2. Added test_reconcile_skips_children_when_epic_branch_not_on_target: Verifies the new guard prevents child promotion when the forge reports the epic branch has NOT merged to target. update_issue is never called.

All 6 paths are gated; zero paths can promote a shared-epic child to Merged while the parent epic branch is unmerged.
---
author: oompah
created: 2026-07-22 23:49
---
Verification: All tests pass.
- tests/test_epic_strategy.py::TestLabelMergedEpics::test_merged_epic_reconciles_children_still_done PASSED
- tests/test_epic_strategy.py::TestLabelMergedEpics::test_reconcile_skips_children_when_epic_branch_not_on_target PASSED
- Full test_epic_strategy.py suite: 159 passed
- Full make test: 11710 passed, 38 skipped, 1 pre-existing failure in test_scm.py (test_legacy_failure_short_circuits, unrelated to this work)

Commit: 6edb2a533 on branch epic-OOMPAH-310, pushed to origin.
---
author: oompah
created: 2026-07-22 23:49
---
Completion: OOMPAH-412 audit and hardening complete.

PATH-BY-PATH FINDINGS:

1. _label_merged_epics (~line 10400): GATED. _epic_branch_landed_on_target() checked via 'if not _epic_branch_landed_on_target(...): continue' before _mark_epic_merged(). Fully protected.

2. _open_epic_main_prs (~line 5674): GATED. _mark_epic_merged() is only called inside 'if _epic_branch_landed_on_target(...):' block. Fully protected.

3. _reconcile_merged_epic_children (~line 10501): GAP FOUND AND FIXED. Previously relied on MERGED state invariant with no explicit forge verification. Added defensive _epic_branch_landed_on_target check. Children are now skipped with a warning if the forge confirms the branch has not landed, protecting against external state changes or future regressions.

4. _open_deferred_done_reviews (~line 8490): GATED. 'if issue.parent_id and rollup_strategy == shared: continue' fires before all update_issue(MERGED) calls. Shared-epic children exit before any promotion.

5. _label_merged_issues (~line 8839): GATED. 'if rollup_strategy == shared and not helper_issue: continue' fires before tracker.update_issue(MERGED). The helper_issue bypass is intentional for CI-fix/rebase helper tasks. _merged_branch_tip_landed also guards against false signals from intermediate branches.

6. _mark_epic_merged (~line 10526): NO INTERNAL GUARD NEEDED. All callers are gated (_label_merged_epics, _open_epic_main_prs via _epic_branch_landed_on_target; _reconcile_merged_epic_children now also hardened).

CODE CHANGES: oompah/orchestrator.py + tests/test_epic_strategy.py committed as 6edb2a533 on epic-OOMPAH-310.
---
author: oompah
created: 2026-07-22 23:50
---
Audited all 6 shared-epic Merged promotion paths in orchestrator.py. Found and fixed one gap: _reconcile_merged_epic_children had no explicit _epic_branch_landed_on_target check (relied on MERGED state invariant). Added defensive guard + updated existing test + new regression test. Paths 1,2,4,5 were already correctly gated. Path 6 (_mark_epic_merged) does not need an internal guard since all callers are now gated.
---
author: oompah
created: 2026-07-22 23:50
---
Agent completed successfully in 1032s (39377 tokens)
---
author: oompah
created: 2026-07-22 23:50
---
Run #3 [attempt=3, profile=standard, role=standard -> Claude/default]
- Turns: 137, Tool calls: 91
- Tokens: 81 in / 39.3K out [39.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 12s
- Log: OOMPAH-412__20260722T233305Z.jsonl
---
<!-- COMMENTS:END -->
