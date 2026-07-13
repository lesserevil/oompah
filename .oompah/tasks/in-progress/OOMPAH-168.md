---
id: OOMPAH-168
type: task
status: In Progress
priority: 1
title: Simplify orchestration to the shared epic workflow
parent: OOMPAH-166
children: []
blocked_by:
- OOMPAH-167
labels: []
assignee: null
created_at: '2026-07-13T02:23:07.456716Z'
updated_at: '2026-07-13T03:56:10.448433Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d34b4d1f-4d76-4d78-aae9-b001549088f7
oompah.task_costs:
  total_input_tokens: 204
  total_output_tokens: 89782
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 204
      output_tokens: 89782
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 204
    output_tokens: 89782
    cost_usd: 0.0
    recorded_at: '2026-07-13T03:13:51.543342+00:00'
---
## Summary

Remove all flat and stacked branches from epic decomposition, task dispatch, branch/worktree selection, review/merge reconciliation, repair tasks, and roll-up status handling. Retain the shared workflow: one epic branch, child work commits to that branch, and the epic PR lands the work on the configured target/default branch. Delete obsolete fallback behavior and strategy-specific code paths rather than retaining dormant compatibility branches. Add regression tests covering decomposition, dispatch, child completion, repair/rebase, nested epics where supported, and epic landing.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 02:33
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 02:34
---
UNDERSTANDING: No duplicate found. OOMPAH-168 is a unique child of epic OOMPAH-166 covering the orchestration layer. Sibling OOMPAH-167 (config/domain layer) is Done and unblocks this task. Scope: remove flat/stacked strategy code paths from orchestrator.py epic decomposition, task dispatch, branch/worktree selection, review/merge reconciliation, repair tasks, and roll-up status handling. Retain only shared workflow logic. Add regression tests. Plan: (1) Read orchestrator.py and related files to find all epic_strategy conditionals, (2) Remove flat/stacked branches, (3) Simplify to shared-only paths, (4) Add/update tests, (5) Run make test.
---
author: oompah
created: 2026-07-13 02:39
---
DISCOVERY: Found all relevant code paths in oompah/orchestrator.py (17740 lines). Key changes needed: (1) _project_epic_strategy() always returns 'shared' — remove flat fallback; (2) Remove all strategy=='stacked' blocks (never true); (3) Remove all 'strategy not in (stacked, shared)' guards (always false → remove the skip); (4) Simplify 'strategy in (stacked, shared)' → keep body unconditionally; (5) Simplify 'strategy == shared' → keep body unconditionally. Affects ~25 sites across epic decomposition, dispatch, branch selection, review reconciliation, repair tasks, and rollup status. Also need to update tests in test_epic_strategy.py (strategy resolution tests) and related test files. No duplicate found — this is unique orchestration work not covered by OOMPAH-167 (config layer) or any other task.
---
author: oompah
created: 2026-07-13 03:13
---
Agent failed: Reached maximum number of turns (200). Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-13 03:13
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 341, Tool calls: 223
- Tokens: 204 in / 89.8K out [90.0K total]
- Cost: $0.0000
- Exit: error, Duration: 40m 18s
- Log: OOMPAH-168__20260713T023338Z.jsonl
---
author: oompah
created: 2026-07-13 03:15
---
Retrying (attempt #3, agent: standard)
---
author: oompah
created: 2026-07-13 03:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 03:56
---
IMPLEMENTATION: Removed all flat and stacked strategy code paths from orchestrator.py (~650 lines deleted). Key changes: (1) _project_epic_strategy() now always returns 'shared' — flat fallback and all lookup code removed; (2) Removed _stacked_child_default_landing_status() entirely; (3) All 'strategy=stacked' blocks removed from _label_merged_issues, _reconcile_stale_in_review_tasks, _merged_branch_tip_landed, _ensure_review_exists, _yolo_epic_strategy_block_reason, _open_epic_main_prs, _all_non_terminal_epics, _label_merged_epics, dispatch gating, _open_deferred_done_reviews; (4) All 'strategy not in (stacked, shared)' guards removed; (5) All 'strategy in (stacked, shared)' guards simplified to unconditional bodies; (6) Docstrings updated to remove strategy-parameterised language. Tests updated: removed 13 stacked/flat-mode tests, added TestEpicRollupChildStrategy (5 tests), test_shared_done_child_with_merged_branch_skips_all_checks, test_shared_child_pr_targeting_epic_branch_is_closed; updated assertions in test_epic_auto_close.py and test_epic_strategy.py for shared-only behavior.
---
<!-- COMMENTS:END -->
