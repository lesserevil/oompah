---
id: OOMPAH-311
type: task
status: Open
priority: null
title: Diagnose and surface remediation path for existing independently-merged child
  branches/PRs
parent: OOMPAH-307
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:53:58.500869Z'
updated_at: '2026-07-22T05:30:26.556478Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 11a99406-9815-48a8-947d-c9aff2dd4fd7
oompah.task_costs:
  total_input_tokens: 308540
  total_output_tokens: 2019
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 308540
      output_tokens: 2019
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 308540
    output_tokens: 2019
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:30:23.701705+00:00'
---
## Summary

Diagnose and provide remediation for independently merged shared-epic child branches and PRs.
## Context

OOMPAH-286 was a child of epic OOMPAH-285 but received its own branch (OOMPAH-286) and PR #466 which merged to main. This is the exact bug OOMPAH-307 wants to prevent. The existing data cannot be reverted (history preserved), but the system should:
1. Detect that a shared-epic child has an independently-merged PR to main (not to the epic branch)
2. Surface a clear operator message without corrupting the epic branch or rewriting history
3. Ensure the detection path is safe and non-destructive

## Implementation scope

1. Add a diagnostic scan in the orchestrator reconciliation loop (or in _epic_auto_close_check / _open_epic_main_prs) that detects shared-epic children whose work_branch (or branch_name) was merged directly to the project's default_branch (not the parent epic branch).

2. When detected, add a tracker comment on the affected child with:
   - 'Detected independent branch merge: branch <X> was merged to <default_branch> via PR #<N> instead of through the parent epic <Y> on branch epic-<Y>. Commits are preserved in <default_branch>. The parent epic OOMPAH-285 branch may not contain these commits. Operator action: cherry-pick <branch> commits to epic-<Y> if missing, then close PR or mark this task as reconciled.'
   - Log the diagnostic at WARNING level

3. Add a tracker label (e.g., needs:reconcile) to the affected child and do NOT promote it to Merged (it's already been merged independently so standard Merged promotion is confusing).

4. Ensure the parent epic's _epic_auto_close_check treats independently-merged children as 'merged_summaries' (already-handled, per the existing 'merged directly to {target_branch}' branch at line 4932) so the epic is not permanently stuck.

5. Ensure the implementation does NOT modify git history, force-push, or close/reopen PRs that are already merged.

## Relevant files
- oompah/orchestrator.py: _epic_auto_close_check (~line 4877+), _open_epic_main_prs (~line 5349), existing 'merged directly to target_branch' handling at ~line 4932

## Tests required
- Test that a shared-epic child whose branch is in merged_branches (to default_branch, not epic branch) triggers the diagnostic comment
- Test that the diagnostic does not crash when the child PR is already closed/merged
- Test that the parent epic is not stuck (the independently-merged child is treated as reconciled for epic completion purposes)
- Fixture mimicking the OOMPAH-286/PR #466 scenario: child.branch_name='OOMPAH-286', PR merged to main; verify diagnostic is posted and epic is not permanently blocked

## Acceptance criteria
- Existing independently-merged children are detected and surfaced to operators with actionable remediation instructions
- No git history is rewritten; commits are preserved
- The parent epic is not permanently stuck due to the misrouted child
- A dedicated test fixture prevents regression of the OOMPAH-285/286 routing outcome

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:30
---
Agent completed successfully in 52s (310559 tokens)
---
author: oompah
created: 2026-07-22 05:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 308.5K in / 2.0K out [310.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 52s
- Log: OOMPAH-311__20260722T052934Z.jsonl
---
author: oompah
created: 2026-07-22 05:30
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-307`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
