---
id: OOMPAH-426
type: bug
status: In Progress
priority: 1
title: Block child task PRs from merging to main before their epic completes
parent: null
children:
- OOMPAH-427
- OOMPAH-428
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T21:15:59.630196Z'
updated_at: '2026-07-23T21:52:15.117932Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 253ce0a7-8fd3-49ec-b846-7a07a833082a
oompah.task_costs:
  total_input_tokens: 366555
  total_output_tokens: 27364
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 366555
      output_tokens: 27364
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 51
    output_tokens: 21301
    cost_usd: 0.0
    recorded_at: '2026-07-23T21:24:46.606259+00:00'
  - profile: deep
    model: unknown
    input_tokens: 366436
    output_tokens: 4094
    cost_usd: 0.0
    recorded_at: '2026-07-23T21:26:49.077715+00:00'
  - profile: deep
    model: unknown
    input_tokens: 68
    output_tokens: 1969
    cost_usd: 0.0
    recorded_at: '2026-07-23T21:34:30.406048+00:00'
---
## Summary

Bug observed on EXOCOMP-57: although it is a child of still-open epic EXOCOMP-9 in a shared-epic project, it opened and YOLO-merged PR #1 directly from EXOCOMP-57 to main. Enforce the merge gate so a non-terminal child task with a parent epic cannot create, approve, or merge a PR targeting the project target branch/main; child work must land on the parent epic branch and only the completed epic may merge to main. Cover PR creation, YOLO merge/reconciliation, and any branch/work_branch override path with regression tests reproducing EXOCOMP-57. Ensure a clear Needs Human handoff if an existing invalid PR requires operator action. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 21:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 21:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 21:23
---
Understanding: Investigating OOMPAH-426 as Duplicate Investigator. The bug describes EXOCOMP-57, a child of still-open epic EXOCOMP-9 in a shared-epic project, which opened and YOLO-merged PR #1 directly from EXOCOMP-57 to main, bypassing the epic branch gate.
---
author: oompah
created: 2026-07-23 21:24
---
Discovery: Duplicate screening complete — NO confirmed duplicate found.

Scope searched:
- All .oompah/tasks/ (archived, backlog, done, merged, open) — 200+ tasks
- oompah/ source tree for relevant functions (_yolo_epic_strategy_block_reason, _ensure_review_exists, _close_invalid_epic_policy_review, shared_epic)
- Git log for related commits
- Candidate tasks reviewed via oompah task view

Closest candidates reviewed and ruled out as duplicates:

**OOMPAH-307 (Merged)**: 'Keep shared-epic child work and merge state on the epic branch' — This is the parent epic that covers the SAME CATEGORY of bug (OOMPAH-286/PR #466 pattern: child assigned own branch + PR to main). However, OOMPAH-307 and ALL its children (308, 309, 310, 311, 312, 313) were completed and merged. OOMPAH-426 describes a REGRESSION — the bug recurring on a different project (EXOCOMP) after OOMPAH-307 fixes were applied. NOT a duplicate.

**OOMPAH-309 (Merged)** / **OOMPAH-404 (Merged)**: Hardened 3 orchestrator.py call sites to fail-closed when _resolve_parent_epic returns None for a child with parent_id. Covers the tracker-error path but not all bypass paths. OOMPAH-426 may indicate a gap not covered by OOMPAH-404.

**OOMPAH-412 (Merged)** / **OOMPAH-413 (Merged)**: Audited and added regression tests for shared-epic Merged promotion paths. Covered _reconcile_merged_epic_children, _label_merged_epics, etc. but not PR creation/YOLO merge gates for child tasks with work_branch override.

**OOMPAH-313 (Merged)**: Regression tests for OOMPAH-285/286 routing. Notably found _resolve_task_for_branch raises → gate fails OPEN (intentional for unrelated PRs). This may be the surviving gap EXOCOMP-57 exploits.

Key differentiator: OOMPAH-426 explicitly mentions 'branch/work_branch override path' which suggests a code path where the child's work_branch or branch is explicitly set/overridden to a non-epic branch (e.g., 'EXOCOMP-57' instead of 'epic-EXOCOMP-9'), and this override is not caught by the existing gates.

Relevant code locations:
- oompah/orchestrator.py: _yolo_epic_strategy_block_reason (~line 12090), _close_invalid_epic_policy_review (~line 12174), _ensure_review_exists (~line 8138), _create_workspace_for_issue (~line 5000)
- tests/test_epic_strategy.py: TestYoloEpicStrategyBlockReason, TestCloseInvalidEpicPolicyReview, TestEnsureReviewExistsRespectsEpicStrategy
- models.py line 26: comment references OOMPAH-286/PR #466 as the known bypass pattern
---
author: oompah
created: 2026-07-23 21:24
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-426 is a unique, fresh regression report of a child-task PR bypassing the shared-epic gate and merging directly to main.

2. Relevant files, commands, evidence, and decisions:
   - oompah/orchestrator.py: _yolo_epic_strategy_block_reason (~line 12090) — YOLO gate that blocks child PRs; fails-open if _resolve_task_for_branch cannot find the task for the branch. _ensure_review_exists (~line 8138) — prevents per-child PR creation; blocks when parent_id set. _close_invalid_epic_policy_review (~line 12174) — closes stale child PRs. _create_workspace_for_issue (~line 5000) — routes child dispatch to epic worktree.
   - tests/test_epic_strategy.py: TestYoloEpicStrategyBlockReason (8 tests), TestCloseInvalidEpicPolicyReview (8 tests), TestEnsureReviewExistsRespectsEpicStrategy — existing regression coverage from OOMPAH-313.
   - Prior epic: OOMPAH-307 (Merged) addressed the OOMPAH-286/PR #466 pattern. All children (OOMPAH-308 through OOMPAH-313) are complete. OOMPAH-426 demonstrates a surviving gap.
   - Key surviving gap from OOMPAH-313 investigation: _resolve_task_for_branch raises → _yolo_epic_strategy_block_reason returns None (fail-open by design for unrelated PRs). But this can also be triggered when EXOCOMP-57's branch is not in the branch index.
   - 'branch/work_branch override path' mentioned in description suggests a scenario where issue.work_branch or issue.target_branch is explicitly set to a non-epic branch, bypassing epic dispatch routing.

3. Remaining work and risks:
   - Reproduce the EXOCOMP-57 scenario: child with parent_id set, work_branch=child-name (not epic branch), target_branch=main, YOLO merges PR to main.
   - Identify which gate failed: (a) _ensure_review_exists didn't block PR creation, (b) _yolo_epic_strategy_block_reason returned None allowing merge, or (c) _create_workspace_for_issue created own worktree instead of routing to epic.
   - Fix the gate gap and add regression tests that specifically reproduce EXOCOMP-57 (child PR to main for an open shared-epic project).
   - Cover PR creation, YOLO merge/reconciliation, and branch/work_branch override paths.
   - Ensure Needs Human handoff when an existing invalid PR is found (operator action required).
   - Run make test.
   - Risk: orchestrator.py is large (~19k lines); use targeted grep to navigate.

4. Recommended next focus: feature (backend fix — implement merge gate enforcement and regression tests for EXOCOMP-57 scenario)
---
author: oompah
created: 2026-07-23 21:24
---
Agent completed successfully in 499s (21352 tokens)
---
author: oompah
created: 2026-07-23 21:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 123, Tool calls: 82
- Tokens: 51 in / 21.3K out [21.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 19s
- Log: OOMPAH-426__20260723T211633Z.jsonl
---
author: oompah
created: 2026-07-23 21:24
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 21:24
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-23 21:24
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-23 21:26
---
Agent completed successfully in 111s (370530 tokens)
---
author: oompah
created: 2026-07-23 21:26
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 366.4K in / 4.1K out [370.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 51s
- Log: OOMPAH-426__20260723T212500Z.jsonl
---
author: oompah
created: 2026-07-23 21:26
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-426`. No stronger profile is configured; retrying with 'deep' in 10s (1/3).
---
author: oompah
created: 2026-07-23 21:27
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-23 21:27
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-23 21:30
---
Understanding (Epic Planner): This is a regression bug where EXOCOMP-57 (child of still-open epic EXOCOMP-9) bypassed the shared-epic gate and had its PR merged directly to main.

Root cause identified from code analysis:

**Bug in `_yolo_epic_strategy_block_reason` (~line 12090 of orchestrator.py):**
When the YOLO gate resolves the source_branch to an issue, it calls `_epic_branch_for_issue(issue)` on the CHILD task. If the child has a stale `work_branch` equal to its own identifier (e.g. 'EXOCOMP-57'), `_epic_branch_for_issue` returns that stale value. The next check `if source_branch == issue_epic_branch` then matches (EXOCOMP-57 == EXOCOMP-57), causing the function to RETURN NONE (allow merge), mistaking the child task PR for an epic rollup PR. This is the primary failure gate.

**Parallel bug in `_close_invalid_epic_policy_review` (~line 12161):**
This function also calls `_epic_branch_for_issue(issue)` on the CHILD task to decide whether to close the invalid PR. Same stale work_branch causes `source_branch == issue_epic_branch`, so `source_branch != issue_epic_branch` is False and the close is SKIPPED.

**Fix required:**
Both functions must add: 'exempt as epic rollup PR only when the issue itself is an epic (issue_type == epic).' Non-epic child tasks should never be exempted through this path.

Plan: Decompose into 2 concrete child tasks — (1) fix YOLO gate + close/Needs Human path, (2) fix PR creation gate + reconciliation path + run make test.
---
author: oompah
created: 2026-07-23 21:34
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 40
- Tokens: 68 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 23s
- Log: OOMPAH-426__20260723T212708Z.jsonl
---
<!-- COMMENTS:END -->
