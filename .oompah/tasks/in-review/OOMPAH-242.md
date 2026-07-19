---
id: OOMPAH-242
type: task
status: In Review
priority: null
title: Require actionable descriptions for every auto-decomposed task
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T03:07:58.167396Z'
updated_at: '2026-07-19T03:13:59.005225Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8f58d52d-3619-41b6-a9f0-9359b1dc5038
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 4258
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 20
      output_tokens: 4258
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 20
    output_tokens: 4258
    cost_usd: 0.0
    recorded_at: '2026-07-19T03:13:17.634930+00:00'
---
## Summary

Prevent auto-decomposition from creating title-only tasks that the dispatcher correctly refuses to run.

Scope:
- Validate every decomposition-planner child has a non-empty title and a substantive description before creating any child.
- Reject the entire decomposition plan if any child is invalid, leave the parent undecomposed, and retain the normal retry path.
- Add an explicit AGENTS.md rule requiring descriptions with scope, test requirements, and acceptance criteria for every task created by humans or agents.

Tests:
- Cover a valid plan, a blank description, whitespace-only description, and an invalid mixed plan; assert no child is created for invalid plans.

Acceptance criteria:
- Auto-decomposition never creates an Open task without a description.
- Project instructions clearly require actionable descriptions for all new tasks.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 03:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 03:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:10
---
Run #1 [attempt=1, profile=default, role=— -> Claude/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 11s
---
author: oompah
created: 2026-07-19 03:11
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 03:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:12
---
Focus handoff: duplicate_detector

(1) Outcome: No duplicate found. OOMPAH-242 is a unique task.

(2) Evidence reviewed:
- Searched .oompah/tasks/ (archived, done, merged, in-progress, open) for: 'decompos', 'description.*required', 'validate.*child', 'title-only', 'actionable', 'AGENTS.md', 'planner.*valid'.
- Closest candidate OOMPAH-15: error_watcher generating structured task descriptions for intake validation — different scope (error_watcher auto-filed bugs, not decomposition planner children).
- OOMPAH-30: validates decomposition boundary (GitHub vs native tracker), not description content/validity.
- OOMPAH-158/159: GitHub issue intake body parsing — completely different.
- No existing task covers: validating decomposition-planner children have substantive descriptions before creation, rejecting entire plan on invalid child, or adding AGENTS.md rules.

(3) Remaining work:
- Locate decomposition planner code (likely oompah/epic_planner.py or similar).
- Add validation: non-empty title + substantive description required for every child in the plan.
- Reject entire plan (no children created) if any child is invalid; retain retry path.
- Update AGENTS.md with description requirements (scope, test requirements, acceptance criteria).
- Add tests: valid plan, blank description, whitespace-only description, mixed invalid plan.
- Run make test to confirm all pass.

(4) Recommended next focus: feature (implement the validation + AGENTS.md update).
---
author: oompah
created: 2026-07-19 03:13
---
Agent completed successfully in 138s (4278 tokens)
---
author: oompah
created: 2026-07-19 03:13
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 39, Tool calls: 30
- Tokens: 20 in / 4.3K out [4.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 18s
- Log: OOMPAH-242__20260719T031110Z.jsonl
---
author: oompah
created: 2026-07-19 03:13
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-19 03:13
---
Implemented in PR #444: validates every auto-decomposition child before any tracker write, rejects blank titles/descriptions atomically, and adds the actionable-description rule to AGENTS.md. Full make test passed (9,342 tests).
---
author: oompah
created: 2026-07-19 03:13
---
Implementation is awaiting PR #444 merge.
---
author: oompah
created: 2026-07-19 03:13
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 03:13
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-19 03:13
---
Run #1 [attempt=1, profile=standard, role=— -> Claude/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2s
---
<!-- COMMENTS:END -->
