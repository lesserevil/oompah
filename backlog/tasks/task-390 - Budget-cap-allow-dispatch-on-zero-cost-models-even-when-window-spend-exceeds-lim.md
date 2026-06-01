---
id: TASK-390
title: >-
  Budget cap: allow dispatch on zero-cost models even when window spend exceeds
  limit
status: Done
assignee: []
created_date: '2026-05-05 20:23'
updated_date: '2026-06-01 16:01'
labels:
  - feature
  - beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: feature
beads:
  id: oompah-zlz_2-fvt
  state: in_progress
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-fvt
  target_branch: null
  url: null
  created_at: '2026-05-05T20:23:03Z'
  updated_at: '2026-05-05T20:26:41Z'
  closed_at: null
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today _should_dispatch rejects every non-P0 issue once the budget window's spend exceeds the limit, regardless of which model the next dispatch would actually use. That's wasteful when the orchestrator has a configured zero-cost model available — there's no spend reason to refuse dispatch on it. We just configured prov-infapi-01 with nvidia/minimaxai/minimax-m2.7 priced at $0/token (cost_per_1k_input=0, cost_per_1k_output=0); putting `OOMPAH_DEFAULT_FIRST_DISPATCH=true` in .env was supposed to route most work onto it, but right now the budget gate stops everything regardless.

Fix: when the budget is exceeded, _should_dispatch should still permit dispatch if the model that *would* be used for this issue has $0 cost in the resolved provider's model_costs map. The check has to be model-aware, not provider-wide — a provider may carry both free and paid models simultaneously (InferenceAPI carries both MiniMax-free and Sonnet/Opus-paid).

Resolution sequence inside _should_dispatch:
1. Compute the would-be agent profile via _match_agent_profile (or use the default profile if OOMPAH_DEFAULT_FIRST_DISPATCH is true and this is the first attempt).
2. Resolve the provider via _resolve_provider for that profile.
3. Resolve the model via _resolve_model.
4. Look up provider.model_costs[model]. If both cost_per_1k_input and cost_per_1k_output are 0, dispatch is allowed even when budget_exceeded is True. Log a clear "budget exceeded but dispatching <issue> on free-tier model <model>" line.

This pairs cleanly with oompah-zlz_2-17u (default-first-dispatch flag): when both flags are true, an over-budget orchestrator continues to chew through cheap work on MiniMax while paid escalations are paused until the next window rolls.

Doc note: clarifies that the budget cap acts on *paid* spend, with $0 models always allowed. Operators who configure model_costs as a placeholder rather than the real price are warning-flagged.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9d2-4cc5-7d6d-9263-f0636ffb711a
author: oompah
created: 2026-05-05T20:26:42Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9d2-7b50-7b17-a72f-2ac948bd5ffe
author: oompah
created: 2026-05-05T20:26:54Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9d3-2c3a-78ca-8758-06713cf2a564
author: oompah
created: 2026-05-05T20:27:39Z

**Understanding**: The issue requires making _should_dispatch budget-aware at the model level. Currently when _check_budget() returns False (exceeded), ALL non-P0 issues are rejected. The fix: when budget is exceeded, resolve the would-be agent profile/provider/model for the issue, look up provider.model_costs[model], and if both cost_per_1k_input and cost_per_1k_output are 0, allow dispatch regardless of budget state.

**Plan**:
1. Modify _should_dispatch() in orchestrator.py to resolve profile/provider/model when budget is exceeded
2. Check if resolved model has zero cost in provider.model_costs
3. Log a clear message when dispatching on a free-tier model despite budget being exceeded
4. Add 'budget_exceeded_paid' as the reject reason for paid models
5. Add 'free_tier_active' flag to the budget block in get_snapshot()
6. Write tests covering all scenarios in the acceptance criteria
7. Document the behavior
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9d3-84da-74c2-90be-fce026d7ac96
author: oompah
created: 2026-05-05T20:28:02Z

**Discovery**: Found the key code locations:
- _should_dispatch() in orchestrator.py (line ~625) is where the budget check happens
- _check_budget() returns False when budget exceeded
- _resolve_provider() and _resolve_model() are already defined as separate helpers, can be reused
- _match_agent_profile() handles profile selection
- _get_default_catch_all_profile() and default_first_dispatch logic already available in _dispatch()
- provider.get_model_costs(model) returns (cost_per_1k_input, cost_per_1k_output) tuple
- model_costs is dict[str, dict[str, float]] on ModelProvider
- get_snapshot() already has a 'budget' block where we can add 'free_tier_active'

The _should_dispatch method needs a helper _would_dispatch_free_model() that replicates the profile/provider/model resolution logic from _dispatch() to check if the next dispatch would use a bash model.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed and merged on main as commit b6b2628 / PR #61. Closing stale In Progress state; no active agent or worktree remains.
<!-- SECTION:FINAL_SUMMARY:END -->
