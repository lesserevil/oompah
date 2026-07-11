---
id: OOMPAH-165
type: task
status: In Progress
priority: null
title: Fix shared epic landed detection before main merge
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-11T03:24:27.952153Z'
updated_at: '2026-07-11T03:45:46.791790Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b0df5901-e2a0-42cc-9bc4-67e7ca437b05
oompah.task_costs:
  total_input_tokens: 111
  total_output_tokens: 3238
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 111
      output_tokens: 3238
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 111
    output_tokens: 3238
    cost_usd: 0.0
    recorded_at: '2026-07-11T03:44:59.164115+00:00'
---
## Summary

Bug: in shared/stacked epic workflows, oompah can mark a top-level epic Merged after child epics merge into the shared epic branch, even when that shared epic branch has not been merged to the project's default branch. Fix landed-epic detection to verify the merged PR target matches the epic's resolved target branch, add regression tests, and repair the coroot project state so the remaining epic-COROOT-4 -> main integration is visible/actionable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-11 03:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-11 03:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-11 03:40
---
Understanding: Investigated this issue thoroughly. No duplicate found — OOMPAH-162 fixed stacked children bypassing epic branch (reverse direction), OOMPAH-163 fixed dispatch validation. OOMPAH-165 is a unique bug.

Root cause: In nested stacked/shared epic workflows, when child sub-epics (e.g., COROOT-11, COROOT-12) merge their branches INTO the parent epic branch (epic-COROOT-4), _label_merged_epics correctly marks those sub-epics as Merged. However, _reconcile_epic_rollup_statuses then sees all children as Merged, computes epic_rollup_state([Merged, Merged]) = 'Merged', and incorrectly sets the parent epic (COROOT-4) to Merged — even though epic-COROOT-4 has NOT been merged to main.

Second issue: _open_epic_main_prs gates on epic_rollup_state(child_states) != DONE. When all children are Merged (not Done), rollup = Merged != Done → the final epic→main PR never opens.

Third issue (defense-in-depth): _label_merged_epics doesn't verify that the merged PR's target matches the epic's resolved target branch, so an epic could be incorrectly marked Merged if its branch was merged to a wrong intermediate branch.

Plan:
1. Fix _reconcile_epic_rollup_statuses: for stacked/shared epics, cap rolled state at Done when it would be Merged (the Merged transition is owned by _label_merged_epics via PR target verification)
2. Fix _open_epic_main_prs: allow rollup = Merged or Done to open the final PR (children in epic branch = ready for epic→main)
3. Fix _label_merged_epics: add target branch check in fallback find_pr_for_branch path
4. Add regression tests
5. Repair coroot COROOT-4 state
---
author: oompah
created: 2026-07-11 03:45
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 67
- Tokens: 111 in / 3.2K out [3.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 19m 56s
- Log: OOMPAH-165__20260711T032509Z.jsonl
---
author: oompah
created: 2026-07-11 03:45
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-11 03:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-11 03:45
---
Agent completed successfully in 18s
---
author: oompah
created: 2026-07-11 03:45
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: normal, Duration: 18s
- Log: OOMPAH-165__20260711T034519Z.jsonl
---
author: oompah
created: 2026-07-11 03:45
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-165`. Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
<!-- COMMENTS:END -->
