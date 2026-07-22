---
id: OOMPAH-413
type: task
status: Done
priority: null
title: Add regression tests for shared-epic Merged promotion gates in test_epic_strategy.py
parent: OOMPAH-310
children: []
blocked_by:
- OOMPAH-412
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T21:34:25.679338Z'
updated_at: '2026-07-22T23:58:50.319381Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 21d9c5f2-8bb2-4249-a6f5-8ed7f69f9cd4
oompah.task_costs:
  total_input_tokens: 1067437
  total_output_tokens: 6433
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1067437
      output_tokens: 6433
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 276816
    output_tokens: 1753
    cost_usd: 0.0
    recorded_at: '2026-07-22T23:51:14.397122+00:00'
  - profile: standard
    model: unknown
    input_tokens: 790621
    output_tokens: 4680
    cost_usd: 0.0
    recorded_at: '2026-07-22T23:53:23.461333+00:00'
---
## Summary

### Goal
Add regression tests to tests/test_epic_strategy.py that verify shared-epic children are ONLY promoted to Merged after the parent epic's branch is confirmed merged to the target. Cover all promotion paths identified in OOMPAH-412.

### Context
Depends on OOMPAH-412 completing the audit and any hardening. The feature agent on OOMPAH-412 will document which paths were confirmed safe and which (if any) were hardened. This task fills remaining test coverage gaps.

### Existing coverage to review first
tests/test_epic_strategy.py already has:
- TestLabelMergedEpics class (~line 3533): Tests _label_merged_epics paths including no-merge and merge cases.
- test_merged_epic_reconciles_children_still_done (~line 3642): Tests _reconcile_merged_epic_children.
- test_shared_done_child_with_merged_branch_skips_all_checks (~line 2819): Tests deferred Done reviews guard.

### Tests to add (only if not already covered)

1. **_label_merged_epics not-yet-merged gate**: Shared-epic child with epic in Open/In-Progress state and epic branch NOT in merged_branches → child stays at Done, not promoted to Merged. (Verify test_noop_when_epic_branch_not_merged at line ~3580 already covers this, or add it.)

2. **_reconcile_merged_epic_children idempotency**: Epic is in MERGED state with children already all Merged → no additional update_issue calls.

3. **_reconcile_merged_epic_children only fires for MERGED epics**: If epic is in Done/In-Progress state, _all_merged_epics() should NOT return it, so reconciliation should not fire. Write a test that places an epic in Done state and confirms no child promotion occurs via _reconcile_merged_epic_children.

4. **_open_deferred_done_reviews shared guard**: Shared-epic child in Done state has merged branch in _merged_branches → update_issue is NOT called, ensure_review_exists is NOT called. (Verify test_shared_done_child_with_merged_branch_skips_all_checks already covers this, or strengthen it.)

5. **_label_merged_issues shared guard**: A shared-epic child task appears in forge merged branch list → verify it is NOT marked Merged by _label_merged_issues unless rollup_strategy != 'shared'. Write or strengthen test that runs _label_merged_issues with a shared-epic child in the merged branches set.

6. **_open_epic_main_prs already-landed gate**: Epic branch already landed on target → _mark_epic_merged is called and children are marked Merged. (Check for existing coverage in TestOpenEpicMainPrs class at line ~1662.)

### Acceptance criteria
- All 6 scenarios above have explicit test coverage.
- Tests run via 'make test' with no failures.
- No existing tests regress.
- Commit all new/changed tests to OOMPAH-310 branch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 23:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 23:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 23:51
---
Understanding: Performing the required duplicate screen before any test implementation. OOMPAH-413 is scoped to regression coverage for shared-epic Merged-promotion gates; I will compare it with OOMPAH-412's completed audit/hardening and hand off if distinct.
---
author: oompah
created: 2026-07-22 23:51
---
Discovery: No duplicate confirmed. Closest reviewed work is OOMPAH-412 (commit 6edb2a533): it audited all six promotion paths, hardened _reconcile_merged_epic_children with an explicit _epic_branch_landed_on_target guard, and added landed/unlanded reconciliation tests. OOMPAH-413 remains distinct: it is the follow-up test task covering the remaining explicit scenarios in tests/test_epic_strategy.py.
---
author: oompah
created: 2026-07-22 23:51
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate found.\n\nEvidence: searched .oompah/tasks and project docs for OOMPAH-410 through OOMPAH-413, shared-epic Merged promotion, and relevant orchestrator paths. The closest candidate, OOMPAH-412, is a distinct audit/hardening change (commit 6edb2a533) that added _reconcile_merged_epic_children landing verification plus two direct regression tests.\n\nRemaining work: test focus should inspect tests/test_epic_strategy.py, retain/strengthen existing coverage for _label_merged_epics, deferred Done reviews, and _open_epic_main_prs, and add explicit tests for reconciliation idempotency/only-MERGED selection and _label_merged_issues shared-child guard as necessary.\n\nRecommended next focus: test.
---
author: oompah
created: 2026-07-22 23:51
---
Agent completed successfully in 53s (278569 tokens)
---
author: oompah
created: 2026-07-22 23:51
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 276.8K in / 1.8K out [278.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 53s
- Log: OOMPAH-413__20260722T235024Z.jsonl
---
author: oompah
created: 2026-07-22 23:51
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 23:51
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 23:51
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 23:53
---
Agent completed successfully in 121s (795301 tokens)
---
author: oompah
created: 2026-07-22 23:53
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 16
- Tokens: 790.6K in / 4.7K out [795.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 1s
- Log: OOMPAH-413__20260722T235124Z.jsonl
---
author: oompah
created: 2026-07-22 23:53
---
Agent completed without closing this issue (121s (795301 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 23:53
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 23:53
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 23:58
---
Completion: All 6 regression test scenarios are implemented and passing in tests/test_epic_strategy.py (commit 4e0fe8c07 on epic-OOMPAH-310 branch).

Coverage summary:
1. _label_merged_epics not-yet-merged gate: test_noop_when_epic_branch_not_merged (line 3564) - pre-existing
2. _reconcile_merged_epic_children idempotency: test_reconcile_is_noop_when_all_children_already_merged - NEW
3. _reconcile_merged_epic_children only fires for MERGED epics: test_reconcile_ignores_done_epic_until_rollup_is_merged - NEW
4. _open_deferred_done_reviews shared guard: test_shared_done_child_with_merged_branch_skips_all_checks (line 2694) - pre-existing
5. _label_merged_issues shared guard: test_label_merged_issues_does_not_promote_shared_child_branch - NEW
6. _open_epic_main_prs already-landed gate: test_marks_merged_instead_of_reopening_when_epic_already_landed (line 2283) - pre-existing

All 3 new tests pass, all 3 pre-existing tests confirmed passing. Full test run: 11713 passed, 1 pre-existing failure (test_scm.py::TestFetchCiStatus::test_legacy_failure_short_circuits - unrelated to this task).
---
<!-- COMMENTS:END -->
