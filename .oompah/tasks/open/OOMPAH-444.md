---
id: OOMPAH-444
type: task
status: Open
priority: null
title: Deduplicate post-merge Needs Human recovery instructions
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-25T19:55:15.601730Z'
updated_at: '2026-07-25T20:01:27.639911Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 04bb9aa7-8e4d-4808-8b79-47b7a7314b2a
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
<!-- COMMENTS:END -->
