---
id: OOMPAH-346
type: bug
status: In Review
priority: 1
title: Reserve round-robin providers atomically at dispatch time
parent: null
children: []
blocked_by: []
labels:
- provider-selection
- round-robin
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T00:50:14.701022Z'
updated_at: '2026-07-22T02:28:48.501045Z'
work_branch: OOMPAH-346
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/527
review_number: '527'
merged_at: null
oompah.agent_run_id: e055607c-3e53-40c8-a58e-fe3bcdb854be
oompah.task_costs:
  total_input_tokens: 962038
  total_output_tokens: 54350
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 962038
      output_tokens: 54350
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 228422
    output_tokens: 1404
    cost_usd: 0.0
    recorded_at: '2026-07-22T00:56:50.618428+00:00'
  - profile: default
    model: unknown
    input_tokens: 337190
    output_tokens: 2343
    cost_usd: 0.0
    recorded_at: '2026-07-22T01:23:12.222420+00:00'
  - profile: deep
    model: unknown
    input_tokens: 27
    output_tokens: 6272
    cost_usd: 0.0
    recorded_at: '2026-07-22T01:26:22.435294+00:00'
  - profile: default
    model: unknown
    input_tokens: 396361
    output_tokens: 3154
    cost_usd: 0.0
    recorded_at: '2026-07-22T01:31:00.527671+00:00'
  - profile: deep
    model: unknown
    input_tokens: 38
    output_tokens: 41177
    cost_usd: 0.0
    recorded_at: '2026-07-22T02:09:54.026078+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/527
oompah.review_number: '527'
oompah.work_branch: OOMPAH-346
oompah.target_branch: main
---
## Summary

Problem
Round-robin provider roles use least-recently-used ordering, but candidate usage is recorded only after a worker session completes. When tasks dispatch concurrently, every dispatch observes the same stale usage state and selects the same provider (currently Claude). Usage is intentionally per role, so a global 50/50 split is not required; each role must be fair among its eligible candidates.

Implement
- Add an atomic dispatch-time reservation/claim operation to CandidateSelector for round-robin roles. It must select the least-recently-used eligible candidate and immediately persist usage/reservation under the selector lock before another dispatch can resolve that role.
- Use the operation in dispatch target resolution/claiming so concurrent tasks cannot all select the same first candidate.
- Preserve provider failover: if the reserved candidate fails preflight or startup, record the attempt and reserve/select the next eligible candidate without corrupting ordering or repeatedly selecting the failed candidate.
- Do not change priority-role behavior or legacy single-provider profile behavior.
- Ensure state persists across service restart and remains safe when concurrent dispatches use the same role.

Tests
- Unit test N concurrent reservations for a two-candidate round-robin role alternate fairly: for even N, counts differ by no more than one, and never exhibit the all-first-candidate race.
- Unit test separate roles retain independent usage state.
- Orchestrator test concurrent dispatches using the same role produce alternating provider targets before workers complete.
- Failover tests for preflight and startup failure, including that the next dispatch gets the correct next candidate.
- Regression test: five concurrent Claude/Codex dispatches include Codex rather than all selecting Claude.

Acceptance criteria
- A simultaneous batch for a Claude/Codex round-robin role is balanced within one dispatch per provider whenever both are eligible.
- Running-task state shows the actual chosen provider.
- No duplicate candidate selection is caused solely by dispatching before a prior session completes.
- Existing provider-selection and full test suites pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 00:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 00:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 00:56
---
Agent completed successfully in 42s (229826 tokens)
---
author: oompah
created: 2026-07-22 00:56
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 228.4K in / 1.4K out [229.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 42s
- Log: OOMPAH-346__20260722T005611Z.jsonl
---
author: oompah
created: 2026-07-22 00:56
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-346`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 01:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 01:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 01:23
---
Agent completed successfully in 81s (339533 tokens)
---
author: oompah
created: 2026-07-22 01:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 8
- Tokens: 337.2K in / 2.3K out [339.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 21s
- Log: OOMPAH-346__20260722T012154Z.jsonl
---
author: oompah
created: 2026-07-22 01:23
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-346`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 01:24
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-22 01:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 01:26
---
Focus handoff: duplicate_detector

(1) Outcome: No duplicate found. OOMPAH-346 is a unique bug report.

(2) Evidence reviewed:
- Searched all .oompah/tasks/ directories (archived, done, merged, backlog, needs-ci-fix, needs-rebase) for: round-robin, round_robin, CandidateSelector, provider-selection, provider_selection, concurrent dispatch, atomic reserve, least-recently-used, dispatch target reservation
- Searched docs/, plans/, README.md, WORKFLOW.md for the same keywords
- No task in the tracker uses the 'provider-selection' or 'round-robin' labels at all
- Closest candidates reviewed:
  - OOMPAH-177 (Archived): ReleaseAddendumQueue with atomic claim — about release addendums, completely different subsystem
  - OOMPAH-235 (Done): Concurrent native tracker write recovery — about tracker git commits, not provider dispatch
  - OOMPAH-163 (Archived): dispatch target validation — about branch allowlists, not provider selection strategy
- CandidateSelector exists in oompah/roles.py (line 604) — confirmed it is a real class with a round_robin strategy; no existing task covers atomizing its dispatch-time usage recording

(3) Remaining work:
- oompah/roles.py: CandidateSelector.select_candidate() (or equivalent method) must be updated to atomically record usage/reservation under the selector lock at dispatch time rather than after session completion
- oompah/orchestrator.py: The dispatch target resolution/claiming path (around line 13239 and 15093) must use the new atomic reservation operation
- Failover: if a reserved candidate fails preflight/startup, the next eligible candidate must be selected without corrupting LRU ordering
- Tests (per task spec): N concurrent reservations alternate fairly; independent roles retain independent state; orchestrator concurrent-dispatch test; preflight/startup failover tests; five-concurrent Claude/Codex regression test
- Priority-role behavior and legacy single-provider profile behavior must not change

(4) Recommended next focus: feature (backend — implement atomic dispatch-time CandidateSelector.reserve_candidate() method and integrate into orchestrator dispatch path)
---
author: oompah
created: 2026-07-22 01:26
---
Agent completed successfully in 144s (6299 tokens)
---
author: oompah
created: 2026-07-22 01:26
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/default]
- Turns: 63, Tool calls: 44
- Tokens: 27 in / 6.3K out [6.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 24s
- Log: OOMPAH-346__20260722T012402Z.jsonl
---
author: oompah
created: 2026-07-22 01:26
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 01:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 01:29
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 01:31
---
Agent completed successfully in 89s (399515 tokens)
---
author: oompah
created: 2026-07-22 01:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 10
- Tokens: 396.4K in / 3.2K out [399.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 29s
- Log: OOMPAH-346__20260722T012934Z.jsonl
---
author: oompah
created: 2026-07-22 01:31
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-346`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 01:41
---
Retrying (attempt #4, agent: deep)
---
author: oompah
created: 2026-07-22 01:41
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 01:46
---
Understanding (Test Engineer, attempt #4): The CandidateSelector class in oompah/roles.py has ordered_candidates() and record_used() as separate operations. When N tasks dispatch concurrently, all calls to ordered_candidates() read the same stale state and return the same first candidate. The fix requires a reserve_candidate() method that atomically selects LRU candidate + stamps it under the selector lock in one call. This session will: (1) implement reserve_candidate() in CandidateSelector, (2) update orchestrator._resolve_dispatch_targets() to use it for round-robin roles, (3) write comprehensive tests per the task spec.
---
author: oompah
created: 2026-07-22 02:07
---
Implementation: Added CandidateSelector.reserve_candidate() in oompah/roles.py. This method atomically selects the LRU candidate and stamps it under the selector lock BEFORE returning — so concurrent calls see the updated state and select different candidates. Modified _resolve_dispatch_targets() in orchestrator.py to call reserve_candidate() for round-robin roles instead of ordered_candidates(), ensuring atomic dispatch-time reservation. Priority roles and legacy single-provider profiles are untouched.
---
author: oompah
created: 2026-07-22 02:07
---
Verification: Full test suite (11238 passed, 36 skipped) — all passing. New tests added: (1) 34 tests in test_candidate_selector.py covering reserve_candidate() basics, atomicity, concurrent fairness, exclude, independent roles, and persistence. (2) 17 tests in tests/test_round_robin_atomic_dispatch.py covering concurrent dispatch alternation, preflight failover, startup failover, Claude/Codex 5-concurrent regression, priority non-regression, and legacy single-provider non-regression. Verified that old ordered_candidates() behavior causes the race (20 concurrent calls → all select same provider); new reserve_candidate() distributes fairly.
---
author: oompah
created: 2026-07-22 02:09
---
Completion: Delivered atomic round-robin dispatch-time reservation (OOMPAH-346). Added CandidateSelector.reserve_candidate() that atomically selects LRU + stamps under lock. Updated _resolve_dispatch_targets() to use it for round-robin roles. Added 51 new tests (34 unit + 17 orchestrator-level). Full suite: 11238 passed. Branch OOMPAH-346 pushed to origin.
---
author: oompah
created: 2026-07-22 02:09
---
Added CandidateSelector.reserve_candidate() for atomic dispatch-time LRU selection with immediate stamping under lock. Updated _resolve_dispatch_targets() to use it for round-robin roles, fixing the all-first-candidate race. 51 new tests cover fairness (N concurrent reserves), failover (preflight/startup), Claude/Codex 5-concurrent regression, priority non-regression, and persistence across service restart. All 11238 tests passing.
---
author: oompah
created: 2026-07-22 02:09
---
Agent completed successfully in 1724s (41215 tokens)
---
author: oompah
created: 2026-07-22 02:09
---
Run #5 [attempt=5, profile=deep, role=deep -> Claude/default]
- Turns: 74, Tool calls: 44
- Tokens: 38 in / 41.2K out [41.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 28m 44s
- Log: OOMPAH-346__20260722T014113Z.jsonl
---
author: oompah
created: 2026-07-22 02:09
---
Review handoff deferred: the task branch has unmerged work, but this project is at its open review limit.

Branch: `OOMPAH-346`
Target branch: `main`
Unmerged commits: 1 commit
Open reviews: 1/1

oompah will create the review automatically when review capacity is available.

Recent commits:
  7c7d2ed36 OOMPAH-346: Reserve round-robin providers atomically at dispatch time
---
<!-- COMMENTS:END -->
