---
id: OOMPAH-346
type: bug
status: In Progress
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
updated_at: '2026-07-22T01:37:28.096292Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e055607c-3e53-40c8-a58e-fe3bcdb854be
oompah.task_costs:
  total_input_tokens: 962000
  total_output_tokens: 13173
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 962000
      output_tokens: 13173
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
<!-- COMMENTS:END -->
