---
id: OOMPAH-427
type: task
status: Backlog
priority: null
title: Fix YOLO merge gate bypass for child tasks with stale work_branch (EXOCOMP-57
  regression)
parent: OOMPAH-426
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T21:33:43.808978Z'
updated_at: '2026-07-23T21:33:43.808978Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Bug

EXOCOMP-57 (child of open epic EXOCOMP-9) bypassed the shared-epic merge gate and had its PR merged directly to main. The primary failure is in \`_yolo_epic_strategy_block_reason\` (~line 12090 of \`oompah/orchestrator.py\`).

### Root cause

In \`_yolo_epic_strategy_block_reason\`, after resolving the PR's source_branch to a task issue, the function calls:

\`\`\`python
issue_epic_branch = self._epic_branch_for_issue(issue)  # issue = child task!
if source_branch == issue_epic_branch:
    return None  # Mistakenly allows merge as 'epic rollup PR'
\`\`\`

\`_epic_branch_for_issue(issue)\` returns \`issue.work_branch\` if set. For a child task whose \`work_branch\` was never corrected to the epic branch (stale, equals own identifier, e.g. 'EXOCOMP-57'), this returns 'EXOCOMP-57' = source_branch, so the function returns None (allows YOLO merge). The child PR is mistakenly treated as the epic rollup PR.

The same bug exists in \`_close_invalid_epic_policy_review\` (~line 12161): \`_epic_branch_for_issue(issue)\` returns the child's stale work_branch, so \`source_branch != issue_epic_branch\` is False and the invalid PR is not closed.

### Fix required in \`oompah/orchestrator.py\`

### \`_yolo_epic_strategy_block_reason\`

Restructure the function to:
1. If issue has NO parent_id → return None (allow - top-level task, handled by other gates)
2. If issue IS an epic (nested epic rollup PR) → return None (allow - epic's own rollup PR)
3. Resolve parent_epic (fail closed if None - OOMPAH-309 behavior must be preserved)
4. Get parent_epic_branch = \`_epic_branch_for_issue(parent_epic)\`
5. If source_branch == parent_epic_branch → return None (allow - this IS the epic rollup PR)
6. Otherwise → return block reason (child task bypassing epic branch)

The existing test \`test_allows_epic_rollup_pr_when_source_branch_matches_epic_branch\` must continue to pass (with child.work_branch='epic-epic-1' and source_branch='epic-epic-1', parent_epic_branch='epic-epic-1', the check now correctly compares against the parent epic's branch).

### \`_close_invalid_epic_policy_review\`

In the \`elif issue.parent_id\` branch, replace:
\`\`\`python
issue_epic_branch = self._epic_branch_for_issue(issue)  # WRONG: child's branch
if source_branch != issue_epic_branch:
    ...close
\`\`\`
with:
\`\`\`python
parent_epic_branch = self._epic_branch_for_issue(parent_epic)  # CORRECT: epic's branch
if source_branch != parent_epic_branch:
    ...close
\`\`\`

### Needs Human handoff (already exists but verify)

\`_close_invalid_epic_policy_review\` already adds \`needs_human_tail\` and transitions the child task to Needs Human via \`_mark_needs_human\`. After the fix, verify this path fires correctly for the EXOCOMP-57 scenario.

### Tests required (in \`tests/test_epic_strategy.py\`)

Add to \`TestYoloEpicStrategyBlockReason\`:
- \`test_blocks_child_with_stale_own_work_branch_exocomp57\`: child task has \`work_branch='EXOCOMP-57'\`, \`parent_id='EXOCOMP-9'\`, source_branch='EXOCOMP-57', parent_epic branch is 'epic-EXOCOMP-9' → gate MUST block (return non-None reason). This is the direct EXOCOMP-57 regression test.
- \`test_allows_nested_epic_rollup_pr_with_parent_id\`: a NESTED epic (issue_type='epic', parent_id set) whose source_branch matches its OWN work_branch → gate must allow (return None). Ensures nested epic rollups are not broken.

Add to \`TestCloseInvalidEpicPolicyReview\`:
- \`test_closes_child_pr_with_stale_own_work_branch_exocomp57\`: same EXOCOMP-57 scenario → must close the PR and transition child to Needs Human.
- \`test_does_not_close_epic_rollup_pr_whose_source_matches_parent_epic_branch\`: source_branch matches the PARENT EPIC's branch → must NOT close (it's the valid epic rollup PR).

### Acceptance criteria

1. \`_yolo_epic_strategy_block_reason\` blocks a child task PR where source_branch == child.work_branch (stale) != parent_epic_branch
2. \`_close_invalid_epic_policy_review\` closes such a PR and triggers Needs Human
3. Nested epic rollup PRs (issue_type='epic', parent_id set) are still allowed through
4. Epic rollup PRs (source_branch == parent_epic_branch) are still allowed through
5. All existing tests in TestYoloEpicStrategyBlockReason and TestCloseInvalidEpicPolicyReview still pass
6. \`make test\` passes

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

