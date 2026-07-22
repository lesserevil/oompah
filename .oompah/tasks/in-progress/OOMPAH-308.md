---
id: OOMPAH-308
type: task
status: In Progress
priority: null
title: Fix stale work_branch metadata for native shared-epic children and update to
  epic branch on dispatch
parent: OOMPAH-307
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:52:58.139774Z'
updated_at: '2026-07-22T05:40:21.741472Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 00df7b76-18fe-43f6-9816-7146ca21dc67
oompah.task_costs:
  total_input_tokens: 804264
  total_output_tokens: 3569
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 804264
      output_tokens: 3569
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 387141
    output_tokens: 1734
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:26:58.405306+00:00'
  - profile: default
    model: unknown
    input_tokens: 417123
    output_tokens: 1835
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:36:08.625046+00:00'
---
## Summary

Correct stale shared-epic child branch metadata when dispatching to the parent epic branch.
## Context

When a native (oompah_md) child task has pre-existing work_branch/branch_name metadata in its frontmatter (e.g., from a prior erroneous dispatch), the field is preserved in the in-memory Issue object. Even when _create_workspace_for_issue correctly routes the child to the parent epic worktree, issue.work_branch still holds the stale per-task value (e.g., 'OOMPAH-286' instead of 'epic-OOMPAH-285').

This stale branch is used by _branch_for_issue (lines 7680-7695 in orchestrator.py) in downstream code:
- Done→Merged promotion checks if the per-task branch is in merged_branches; if it is, it may mark the child Merged even though the rollup_strategy guard should catch it
- _ensure_review_exists uses the branch to create a review (though this is guarded by parent_epic check)

## Implementation scope

1. In _create_workspace_for_issue (oompah/orchestrator.py ~line 4767), when routing to the parent epic worktree (parent_epic is not None):
   - Clear issue.work_branch and issue.branch_name from the child's in-memory state (or overwrite with the epic branch name)
   - For oompah_md tracker_kind tasks: call tracker.set_metadata_field(child_id, 'oompah.work_branch', epic_branch_name) to persist the correction to the frontmatter
   - For github_issues tracker_kind children: update the work_branch metadata similarly

2. Ensure the epic branch name (from project_store.epic_branch_name(parent_epic.identifier)) is written as work_branch on the child so _branch_for_issue returns the correct value.

## Relevant files
- oompah/orchestrator.py: _create_workspace_for_issue (~line 4719), _branch_for_issue (~line 7680)
- oompah/oompah_md_tracker.py: set_metadata_field (~line 775)

## Tests required
- test_epic_strategy.py: Add test case where a shared-epic child has work_branch='TASK-1.1' (stale per-task branch) in its issue metadata; after _create_workspace_for_issue, confirm issue.work_branch is updated to the epic branch name, not the per-task value
- Test that set_metadata_field is called on the tracker with the corrected epic branch for oompah_md tasks
- Regression: _branch_for_issue returns epic branch (not stale per-task branch) for a shared-epic child after dispatch routing

## Acceptance criteria
- Shared-epic children dispatched via oompah_md have work_branch set to the parent epic branch, not a per-task branch
- _branch_for_issue(child) returns the epic branch name after routing
- Existing stale work_branch in frontmatter is overwritten on dispatch

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:26
---
Agent completed successfully in 252s (388875 tokens)
---
author: oompah
created: 2026-07-22 05:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 387.1K in / 1.7K out [388.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 12s
- Log: OOMPAH-308__20260722T052248Z.jsonl
---
author: oompah
created: 2026-07-22 05:27
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-307`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 05:27
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 05:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:36
---
Agent completed successfully in 56s (418958 tokens)
---
author: oompah
created: 2026-07-22 05:36
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 7
- Tokens: 417.1K in / 1.8K out [419.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 56s
- Log: OOMPAH-308__20260722T053516Z.jsonl
---
author: oompah
created: 2026-07-22 05:36
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-307`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 05:36
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 05:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:40
---
Agent failed: Exception: Control request timeout: initialize. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-07-22 05:40
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3m 51s
- Log: OOMPAH-308__20260722T053630Z.jsonl
---
<!-- COMMENTS:END -->
