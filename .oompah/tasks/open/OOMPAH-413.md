---
id: OOMPAH-413
type: task
status: Open
priority: null
title: Add regression tests for shared-epic Merged promotion gates in test_epic_strategy.py
parent: OOMPAH-310
children: []
blocked_by:
- OOMPAH-412
labels: []
assignee: null
created_at: '2026-07-22T21:34:25.679338Z'
updated_at: '2026-07-22T23:28:00.456102Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

