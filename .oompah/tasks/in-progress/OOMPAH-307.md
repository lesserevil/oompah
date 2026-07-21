---
id: OOMPAH-307
type: bug
status: In Progress
priority: 1
title: Keep shared-epic child work and merge state on the epic branch
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:27:57.025790Z'
updated_at: '2026-07-21T16:45:49.009686Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: aca18f5f-afa9-4002-af74-d7d05ca7724c
oompah.task_costs:
  total_input_tokens: 255429
  total_output_tokens: 2216
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 255429
      output_tokens: 2216
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 255429
    output_tokens: 2216
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:41:14.036695+00:00'
---
## Summary

Fix native Markdown task dispatch so child tasks in a shared epic execute on the epic work branch and are not independently merged to main.\n\nObserved reproduction: OOMPAH-286 is a child of epic OOMPAH-285 but was assigned work_branch=OOMPAH-286, target_branch=main, and PR #466. Its status became Merged even though the parent epic branch remains the intended integration branch. Under the shared-only epic model, this child should contribute to OOMPAH-285’s branch and remain non-terminal until the epic is merged.\n\nImplementation requirements:\n- Identify shared epic membership before creating a worktree, branch, PR, or terminal-state transition.\n- Route child commits and tests to the parent epic worktree/work branch; never create a child-to-main PR for a shared child.\n- Record child completion as integrated-on-epic-branch (or equivalent non-terminal state) and show the parent epic/branch in dashboard, detail, CLI/API, and release association views.\n- Promote child tasks to Merged only when the parent epic merge to its target branch is confirmed.\n- Reconcile existing affected children safely: detect independently created child PRs/branches, preserve history, and surface an operator remediation path without rewriting or losing commits.\n\nTests:\n- Shared-epic child dispatch uses parent worktree/branch and creates no child PR to main.\n- Child completion before epic merge is not terminal; after confirmed epic merge it becomes Merged.\n- Regression fixture for OOMPAH-285/OOMPAH-286 routing prevents a child branch/PR #466-style outcome.\n- Existing independently merged child data is diagnosed and does not corrupt the epic branch.\n\nAcceptance criteria:\n- Shared-epic children never bypass the epic branch.\n- UI status explains whether a child is complete on the epic branch versus merged to target.\n- No child is falsely labeled Merged before its epic delivery is merged.\n- Relevant Makefile tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:40
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 16:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:41
---
Agent completed successfully in 62s (257645 tokens)
---
author: oompah
created: 2026-07-21 16:41
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 255.4K in / 2.2K out [257.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 2s
- Log: OOMPAH-307__20260721T164019Z.jsonl
---
author: oompah
created: 2026-07-21 16:41
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-307`. No stronger profile is configured; retrying with 'deep' in 10s (1/3).
---
author: oompah
created: 2026-07-21 16:45
---
Retrying (attempt #3, agent: deep)
---
author: oompah
created: 2026-07-21 16:45
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
