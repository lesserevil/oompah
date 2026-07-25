---
id: OOMPAH-444
type: task
status: Done
priority: null
title: Deduplicate post-merge Needs Human recovery instructions
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-25T19:55:15.601730Z'
updated_at: '2026-07-25T20:02:57.776532Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9c329385-8175-44c8-9078-42e5a5468f83
oompah.task_costs:
  total_input_tokens: 35
  total_output_tokens: 8475
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 35
      output_tokens: 8475
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 35
    output_tokens: 8475
    cost_usd: 0.0
    recorded_at: '2026-07-25T20:01:50.314231+00:00'
---
## Summary

The merged-epic reconciliation pass currently calls mark_needs_human on every scheduler tick for a child that remains Needs Human without landing evidence, appending the identical actionable recovery instruction repeatedly (observed on EXOCOMP-66 and peers). Make this transition idempotent: if the child is already Needs Human and the same normalized instruction has already been posted, do not update status or add another comment; if the landing-evidence reason/instruction changes, post the changed actionable instruction once. Preserve first-transition behavior and the final-comment human-action contract. Add tests reproducing consecutive reconciliation ticks and changed-instruction behavior in tests/test_epic_strategy.py, then run focused and full Make quality gates.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-25 19:55
---
Reproduced in exocomp: merged-epic reconciliation appended the identical landing-evidence recovery instruction on each tick while the child remained Needs Human. Implementing durable tracker-comment dedup keyed by normalized instruction, with changed-instruction coverage.
---
author: oompah
created: 2026-07-25 19:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-25 19:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-25 19:59
---
Understanding: As Duplicate Investigator, I am screening OOMPAH-444 ('Deduplicate post-merge Needs Human recovery instructions') for duplicates before any implementation begins. The issue describes merged-epic reconciliation calling mark_needs_human on every scheduler tick for a child already in Needs Human state, appending the same recovery instruction repeatedly (observed on EXOCOMP-66). I will search for similar tasks in the tracker and codebase before concluding.
---
author: oompah
created: 2026-07-25 20:01
---
Focus handoff: duplicate_detector

1. **Outcome:** No duplicate found. OOMPAH-444 is a unique, first-of-its-kind bug fix for the merged-epic reconciliation Needs Human deduplication problem.

2. **Evidence searched:**
   - All .oompah/tasks/ states (archived, open, backlog, merged, done) — 280+ tasks scanned
   - Patterns: mark_needs_human, needs_human, Needs Human, dedup, idempotent, reconcil, landing_evidence, epic_strategy, EXOCOMP, repeated comment, recovery instruction, scheduler tick, post-merge
   - Source files: oompah/orchestrator.py, tests/test_epic_strategy.py

3. **Closest candidates reviewed and ruled out:**
   - OOMPAH-205 (archived): dashboard WS snapshot dedup — UI layer, entirely different scope
   - OOMPAH-212 (archived): prevent duplicate native task records on board — different problem (duplicate task IDs, not repeated comments)
   - OOMPAH-222 (archived): duplicate native oompah task ID bug — unrelated
   - OOMPAH-28 (archived): state transition audit — covered mark_needs_human in tests but not the repeated-call dedup issue
   - OOMPAH-168/169/170 (archived): epic strategy refactoring (shared-only simplification) — different scope

4. **Root cause confirmed:** In oompah/orchestrator.py at line 11082, the merged-epic reconciliation unconditionally calls `_mark_needs_human(tracker, child.identifier, instruction)` on every scheduler tick for children that remain Needs Human without landing evidence. The `_mark_needs_human` helper (line 14807) does not check whether the task is already in Needs Human state or whether the same instruction was previously posted. Fix needs to: (a) check child_status == NEEDS_HUMAN before calling, (b) compare the normalized instruction against the task's last comment, and (c) only call if status changed or instruction changed. Tests should go in tests/test_epic_strategy.py.

5. **Recommended next focus:** feature (backend fix in oompah/orchestrator.py)
---
author: oompah
created: 2026-07-25 20:01
---
Agent completed successfully in 180s (8510 tokens)
---
author: oompah
created: 2026-07-25 20:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 73, Tool calls: 57
- Tokens: 35 in / 8.5K out [8.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 0s
- Log: OOMPAH-444__20260725T195851Z.jsonl
---
author: oompah
created: 2026-07-25 20:01
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-25 20:02
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-25 20:02
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-25 20:02
---
Understanding: Documentation focus will assess whether this internal merged-epic reconciliation idempotency fix changes any public/operator contract or existing architecture documentation. I will search docs, plans, README, and WORKFLOW for the relevant reconciliation and Needs Human behavior, verify terminology against the implementation, and either make documentation-only updates or record that none are warranted before handing off to the backend feature focus.
---
author: oompah
created: 2026-07-25 20:02
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 10
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 47s
- Log: OOMPAH-444__20260725T200212Z.jsonl
---
author: oompah
created: 2026-07-25 20:02
---
Implemented in fb890bff4. Landed-epic reconciliation now suppresses an unchanged Needs Human recovery instruction after normalizing tracker whitespace, while changed landing evidence still produces a fresh actionable handoff. Added regressions for repeated ticks and changed work branches. Full make test: 12,320 passed, 7 skipped. Repository check-secrets remains blocked only by the pre-existing safe test fixture glpat-REDACTED-for-testing; the changed diff was manually checked and contains no secret material.
---
<!-- COMMENTS:END -->
