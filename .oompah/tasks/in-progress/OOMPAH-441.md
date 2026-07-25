---
id: OOMPAH-441
type: task
status: In Progress
priority: null
title: Resolve shared epic parent lookup for review gates
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-25T01:59:58.245991Z'
updated_at: '2026-07-25T02:04:51.905405Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d25afac9-9e17-4b58-a4a1-bbf07ebc739d
oompah.task_costs:
  total_input_tokens: 27
  total_output_tokens: 8263
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 27
      output_tokens: 8263
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 27
    output_tokens: 8263
    cost_usd: 0.0
    recorded_at: '2026-07-25T02:04:19.304118+00:00'
---
## Summary

Fix the shared-epic review gate when a child task references a valid parent epic but the parent lookup fails, as seen with EXOCOMP-29 and PR #10. Resolve the parent from canonical tracker state where appropriate, preserve fail-closed behavior for genuinely unreachable parents, and add regression tests. Run the relevant Makefile test target and deploy the fix.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-25 02:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-25 02:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-25 02:01
---
Understanding: As Duplicate Investigator, I will search existing tasks for any prior work on the shared-epic review gate parent lookup failure described in this issue (EXOCOMP-29, PR #10). I'll check .oompah/tasks and related docs for candidates before any implementation begins.
---
author: oompah
created: 2026-07-25 02:04
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-441 is a unique, first-of-its-kind issue.

**Evidence searched:**
- All `.oompah/tasks/` states: open (OOMPAH-281), backlog (OOMPAH-282), done (OOMPAH-235), merged (OOMPAH-218–280), archived (OOMPAH-1–232).
- Grep patterns: `shared.epic`, `parent.lookup`, `review.gate`, `EXOCOMP`, `fail.closed`, `review gate`, `parent.*resolve`, `_resolve_parent_epic`, `epic.*parent.*lookup`.
- `docs/`, `plans/`, `README.md`, `WORKFLOW.md` — no hits on the described bug.
- Scanned the actual orchestrator.py code around the review gate logic (lines 8170–8210, 12130–12180): confirmed the `_resolve_parent_epic` fail-closed path at line ~12153 is real and unpatched.

**Closest candidates reviewed and ruled out:**
- **OOMPAH-165** (archived): 'Fix shared epic landed detection before main merge' — this was about _reconcile_epic_rollup_statuses prematurely setting a parent epic to Merged when sub-epics merged into its branch. Completely different code path and bug.
- **OOMPAH-168** (archived): 'Simplify orchestration to shared epic workflow' — removed flat/stacked strategy code, unrelated to parent lookup failures.
- **OOMPAH-163** (archived): 'Oompah-owned epic branches should bypass branch allowlist' — target-branch dispatch validation, not review gate parent lookup.
- No task mentions EXOCOMP-29 or PR #10. No task covers the specific fail-closed path where `_resolve_parent_epic()` returns None for a child with a valid `parent_id`.

**Root cause identified in code:**
In `oompah/orchestrator.py` ~line 12150–12163, `_review_merge_gate_reason()` calls `_resolve_parent_epic(issue)`. When this returns None (e.g., transient or stale cache), the code fails closed with: _'child task {id} has parent {parent_id} but it could not be resolved; blocking PR until parent epic is reachable'_. The fix should: (1) try to resolve the parent from canonical tracker state (e.g., via direct tracker lookup by parent_id), (2) only fail closed when the parent is genuinely unreachable (not just absent from the in-memory cache).

**Relevant files for implementation:**
- `oompah/orchestrator.py`: `_resolve_parent_epic()` (~line 4917), `_review_merge_gate_reason()` (~line 12150), `_maybe_open_deferred_done_reviews()` (~line 8183)
- `tests/test_submit_queue_concurrency.py`: existing review gate tests (~line 401+)
- `tests/test_orchestrator_merged.py`: merged review gate tests (~line 2542)

**Remaining work:**
1. Diagnose why `_resolve_parent_epic()` fails for EXOCOMP-29 (likely a cache miss or tracker read failure)
2. Add a canonical tracker fallback lookup in `_review_merge_gate_reason()` when `_resolve_parent_epic()` returns None but `parent_id` is set
3. Preserve fail-closed behavior only when the tracker lookup also fails
4. Add regression tests reproducing the EXOCOMP-29 / PR #10 scenario
5. Run `make test` and deploy

**Recommended next focus:** feature (backend)
---
author: oompah
created: 2026-07-25 02:04
---
Agent completed successfully in 193s (8290 tokens)
---
author: oompah
created: 2026-07-25 02:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 70, Tool calls: 43
- Tokens: 27 in / 8.3K out [8.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 13s
- Log: OOMPAH-441__20260725T020108Z.jsonl
---
author: oompah
created: 2026-07-25 02:04
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-25 02:04
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-25 02:04
---
Focus: DevOps Engineer
---
<!-- COMMENTS:END -->
