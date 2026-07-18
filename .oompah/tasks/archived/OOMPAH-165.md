---
id: OOMPAH-165
type: task
status: Archived
priority: null
title: Fix shared epic landed detection before main merge
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-11T03:24:27.952153Z'
updated_at: '2026-07-18T04:55:42.270897Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 068a170c-2e21-44de-a75f-108c588d2269
oompah.task_costs:
  total_input_tokens: 256
  total_output_tokens: 7845
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 256
      output_tokens: 7845
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 111
    output_tokens: 3238
    cost_usd: 0.0
    recorded_at: '2026-07-11T03:44:59.164115+00:00'
  - profile: default
    model: unknown
    input_tokens: 86
    output_tokens: 3079
    cost_usd: 0.0
    recorded_at: '2026-07-11T03:52:00.783290+00:00'
  - profile: standard
    model: unknown
    input_tokens: 10
    output_tokens: 59
    cost_usd: 0.0
    recorded_at: '2026-07-11T03:52:34.737443+00:00'
  - profile: default
    model: unknown
    input_tokens: 49
    output_tokens: 1469
    cost_usd: 0.0
    recorded_at: '2026-07-11T03:57:40.931075+00:00'
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
author: oompah
created: 2026-07-11 03:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-11 03:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-11 03:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-11 03:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-11 03:51
---
Understanding: Previous investigation confirmed this is a unique bug (no duplicate). Three distinct fixes needed:

1. _reconcile_epic_rollup_statuses: When all children of a stacked/shared epic are Merged (e.g., sub-epics merged into the parent epic branch), epic_rollup_state returns MERGED, incorrectly setting the parent epic to Merged even though its branch hasn't landed on main. Fix: cap rollup at DONE when strategy is stacked/shared.

2. _open_epic_main_prs: Gates on rollup == DONE to open the final epic→main PR. But if all children are Merged, rollup is MERGED != DONE, so the PR never opens. Fix: allow MERGED in addition to DONE.

3. _label_merged_epics: Fallback path (find_pr_for_branch) marks epic landed if ANY PR from its branch is merged, without verifying the PR target is the epic's resolved target branch. Fix: add target branch check.

4. COROOT-4 state repair: The bug incorrectly marked COROOT-4 as Merged. Need to move it back to Done so _open_epic_main_prs can open the epic-COROOT-4 → main PR.

Starting implementation now.
---
author: oompah
created: 2026-07-11 03:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 64
- Tokens: 86 in / 3.1K out [3.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 40s
- Log: OOMPAH-165__20260711T034725Z.jsonl
---
author: oompah
created: 2026-07-11 03:52
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-11 03:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-11 03:52
---
Agent completed successfully in 18s (69 tokens)
---
author: oompah
created: 2026-07-11 03:52
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 3
- Tokens: 10 in / 59 out [69 total]
- Cost: $0.0000
- Exit: normal, Duration: 18s
- Log: OOMPAH-165__20260711T035220Z.jsonl
---
author: oompah
created: 2026-07-11 03:52
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-165`. Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-11 03:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-11 03:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-11 03:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-11 03:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-11 03:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 33
- Tokens: 49 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 28s
- Log: OOMPAH-165__20260711T035417Z.jsonl
---
author: oompah
created: 2026-07-11 03:57
---
Fixed the shared/stacked epic state bug and recovered coroot. Oompah commits pushed: f5269a44 made epic landing target-aware and allowed terminal child epics to unblock parent PRs; 2820f322 prevents shared/stacked child-only Merged rollups from marking the parent epic Merged before its branch lands. Full make test passed. Rebuilt and force-pushed coroot epic-COROOT-4 on current main without .oompah/tasks changes, opened PR #39, and moved COROOT-4 to In Review with review metadata.
---
<!-- COMMENTS:END -->
