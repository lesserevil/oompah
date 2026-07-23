---
id: OOMPAH-428
type: task
status: In Progress
priority: null
title: Harden PR creation gate and work_branch reconciliation for shared-epic child
  tasks
parent: OOMPAH-426
children: []
blocked_by:
- OOMPAH-427
labels: []
assignee: null
created_at: '2026-07-23T21:34:08.303204Z'
updated_at: '2026-07-23T22:12:58.238523Z'
work_branch: epic-OOMPAH-426
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ba072b55-6de2-46c2-9a35-95a735117575
oompah.work_branch: epic-OOMPAH-426
oompah.task_costs:
  total_input_tokens: 727357
  total_output_tokens: 3197
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 727357
      output_tokens: 3197
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 727357
    output_tokens: 3197
    cost_usd: 0.0
    recorded_at: '2026-07-23T22:12:35.974614+00:00'
---
## Summary

### Context

This is the defense-in-depth companion to OOMPAH-427 (YOLO gate fix). While OOMPAH-427 patches the merge-time gate, this task audits and hardens the earlier gates: PR creation (\`_ensure_review_exists\`) and branch/work_branch reconciliation (\`_create_workspace_for_issue\`).

OOMPAH-427 must be merged before this task starts.

### Scope

### 1. Audit \`_ensure_review_exists\` (~line 8138 of \`oompah/orchestrator.py\`)

Current logic blocks per-child PR creation via:
\`\`\`python
if (entry.issue is not None and (entry.issue.parent_id or '').strip()):
    return True  # no per-child PR
\`\`\`

Potential gap: if \`entry.issue.parent_id\` is absent due to a partial load or tracker error, the function falls through and may create a per-child PR. Harden this path:
- If \`entry.issue\` has no parent_id but the parent CAN be resolved (via \`_resolve_parent_epic\` or tracker lookup), block PR creation and fail closed
- Add a diagnostic log line when blocking due to resolved parent

### 2. Audit \`_create_workspace_for_issue\` (~line 5001 of \`oompah/orchestrator.py\`)

The function corrects stale \`work_branch\` on the child before routing to the epic worktree:
\`\`\`python
if current_child_branch != epic_branch:
    issue.work_branch = epic_branch
    issue.branch_name = epic_branch
    tracker.set_metadata_field(issue.identifier, 'oompah.work_branch', epic_branch)
\`\`\`

Edge case: the \`set_metadata_field\` call may fail silently (TrackerError is caught and logged). If the correction is NOT persisted, subsequent orchestrator restarts see the stale work_branch again, which is what EXOCOMP-57 exploited. This is already the current behavior, but verify the in-memory correction is always applied even when the tracker write fails. No change required if it is.

### 3. Work_branch override path in reconciliation

The reconciliation path (\`_reconcile_independently_merged_children\`) detects children that bypassed the epic branch AFTER the fact (MERGED state). Verify it correctly labels the EXOCOMP-57 scenario (\`child.work_branch = 'EXOCOMP-57'\`, child state = MERGED, parent epic open or merged, epic_branch = 'epic-EXOCOMP-9'). Add a regression test if it doesn't already cover this.

### Tests required (in \`tests/test_epic_strategy.py\`)

Add to the existing \`TestEnsureReviewExists\` class (around line 1170):
- \`test_shared_child_pr_blocked_even_with_stale_own_work_branch\`: entry.issue has \`parent_id\` set AND \`work_branch\` equal to the child's own identifier (not the epic branch). \`_ensure_review_exists\` must return True without creating a PR.
- \`test_shared_child_pr_blocked_when_parent_id_missing_but_parent_resolvable\` (if the hardening above is implemented): entry.issue.parent_id is None/empty but tracker returns a parent epic. Must block PR creation.

Add/verify in reconciliation tests:
- \`test_detects_independently_merged_child_with_stale_own_work_branch\`: child.work_branch='child-id', epic_branch='epic-parent-id', child state=MERGED → \`_detect_independently_merged_children\` must flag this child.

### Acceptance criteria

1. \`_ensure_review_exists\` never creates a per-child PR when \`issue.parent_id\` is set, regardless of \`work_branch\` value
2. \`_create_workspace_for_issue\` always corrects the child's in-memory \`work_branch\` to the epic branch before routing, even when tracker persistence fails
3. \`_detect_independently_merged_children\` / \`_reconcile_independently_merged_children\` labels the EXOCOMP-57 pattern correctly
4. All existing epic strategy tests still pass
5. \`make test\` passes

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 22:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 22:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 22:12
---
Agent completed successfully in 104s (730554 tokens)
---
author: oompah
created: 2026-07-23 22:12
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 727.4K in / 3.2K out [730.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 44s
- Log: OOMPAH-428__20260723T221057Z.jsonl
---
author: oompah
created: 2026-07-23 22:12
---
Agent completed without closing this issue (104s (730554 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-23 22:12
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 22:12
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
