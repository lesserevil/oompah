---
id: OOMPAH-427
type: task
status: In Progress
priority: null
title: Fix YOLO merge gate bypass for child tasks with stale work_branch (EXOCOMP-57
  regression)
parent: OOMPAH-426
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T21:33:43.808978Z'
updated_at: '2026-07-23T21:57:33.646708Z'
work_branch: epic-OOMPAH-426
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a5fd0f7a-1874-4fcb-895a-eb4b8feea282
oompah.work_branch: epic-OOMPAH-426
oompah.task_costs:
  total_input_tokens: 41
  total_output_tokens: 13525
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 41
      output_tokens: 13525
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 41
    output_tokens: 13525
    cost_usd: 0.0
    recorded_at: '2026-07-23T21:57:12.178855+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 21:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 21:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 21:56
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-427 is a unique, confirmed regression.

**Duplicate screening performed:**
Searched all .oompah/tasks/ files (open, backlog, done, merged, archived) and git log for these patterns: yolo_epic_strategy, epic_strategy_block, close_invalid_epic, work_branch stale, EXOCOMP-57, merge gate bypass, epic_branch_for_issue, issue_epic_branch.

**Closest candidates reviewed and ruled out:**

1. **OOMPAH-308** (merged commit 1e52f6134): "Fix stale work_branch metadata for shared-epic children on dispatch" — Fixes the stale work_branch at DISPATCH TIME in `_create_workspace_for_issue`. Does NOT touch `_yolo_epic_strategy_block_reason` or `_close_invalid_epic_policy_review`. Different fix point.

2. **OOMPAH-309** (merged via epic-OOMPAH-309, commit 8b4521d29): "Harden shared-epic protection when _resolve_parent_epic fails for a child with parent_id set" — Adds fail-closed behavior for when `_resolve_parent_epic` returns None. This is a DIFFERENT failure mode from OOMPAH-427. OOMPAH-427 is about _resolve_parent_epic succeeding but then comparing against the WRONG branch variable.

3. **OOMPAH-413** (commit 4e0fe8c07): "cover shared epic merge promotion gates" — Adds tests for `_label_merged_issues` and `_reconcile_merged_epic_children`. Different functions entirely.

**Bug confirmed present in current code:**

In `_yolo_epic_strategy_block_reason` (orchestrator.py:12131-12133):
```python
issue_epic_branch = self._epic_branch_for_issue(issue)  # BUG: issue = child, not parent epic
if source_branch == issue_epic_branch:
    return None  # incorrectly allows when child.work_branch is stale (= own identifier)
```
`_epic_branch_for_issue` returns `issue.work_branch` if set. For EXOCOMP-57 with stale work_branch='EXOCOMP-57', calling this on the child returns 'EXOCOMP-57' = source_branch → gate incorrectly allows.

Same bug exists in `_close_invalid_epic_policy_review` (orchestrator.py:12235-12238): checks `source_branch != issue_epic_branch` where issue_epic_branch comes from the child, not the parent epic.

**Key files for implementation:**
- `oompah/orchestrator.py` lines 12090-12160 (`_yolo_epic_strategy_block_reason`)  
- `oompah/orchestrator.py` lines 12161-~12280 (`_close_invalid_epic_policy_review`)
- `tests/test_epic_strategy.py` classes `TestYoloEpicStrategyBlockReason` (line 4277) and `TestCloseInvalidEpicPolicyReview` (line 4417)
- `tests/test_epic_strategy.py` helper `_make_shared_epic_scenario` (line 4244)

**Fix required (per issue description):**

In `_yolo_epic_strategy_block_reason`: restructure so the epic-rollup-PR check compares source_branch against the PARENT EPIC's branch (via `_epic_branch_for_issue(parent_epic)`), not the child's own work_branch. Nested epics (issue_type='epic') should return None directly (they are their own rollup PR).

In `_close_invalid_epic_policy_review`: replace `issue_epic_branch = _epic_branch_for_issue(issue)` check with `parent_epic_branch = _epic_branch_for_issue(parent_epic)`.

**Tests required:** 4 new tests as described in the issue (2 in TestYoloEpicStrategyBlockReason, 2 in TestCloseInvalidEpicPolicyReview).

**Remaining work:** Full implementation of the fix + tests + make test. No ambiguity — the issue description is precise.

**Recommended next focus:** feature (bug fix implementation)
---
author: oompah
created: 2026-07-23 21:57
---
Agent completed successfully in 305s (13566 tokens)
---
author: oompah
created: 2026-07-23 21:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 86, Tool calls: 61
- Tokens: 41 in / 13.5K out [13.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 5s
- Log: OOMPAH-427__20260723T215210Z.jsonl
---
author: oompah
created: 2026-07-23 21:57
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 21:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 21:57
---
Focus: Epic Planner
---
<!-- COMMENTS:END -->
