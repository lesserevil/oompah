---
id: OOMPAH-562
type: bug
status: In Progress
priority: 1
title: Recover integration queues blocked by stale epic ancestry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:08:21.827812Z'
updated_at: '2026-07-29T21:28:06.824530Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9cdd0dccc0633a668b1bb9eda0106229ecc2b0c8e3e4dd82f57bfa96388450cc
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T21:17:53.197353+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Active OOMPAH-281 and OOMPAH-282 are unrelated. Closest\
    \ reviewed terminal tasks\u2014OOMPAH-165, OOMPAH-168, OOMPAH-177, OOMPAH-253,\
    \ and OOMPAH-264\u2014cover adjacent epic detection, orchestration, queueing,\
    \ or rebase behavior but not stale-ancestry recovery for integration queues. No\
    \ files or tracker state were modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 00021a4c-ff96-47d6-b846-ffece2d2f18a
oompah.task_costs:
  total_input_tokens: 910697
  total_output_tokens: 4297
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 910697
      output_tokens: 4297
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 910697
    output_tokens: 4297
    cost_usd: 0.0
    recorded_at: '2026-07-29T21:17:53.194849+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-562__20260729T211610Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-562
    source_sha: 31f8938b8f669a316a830690aaedcc1e0d3834bf
    completed_at: '2026-07-29T21:17:53.207725+00:00'
---
## Summary

Triggered by: OOMPAH-561

Parallel epic integration can deadlock with every submission in Ready to Integrate and attempts=0 when a parent epic branch predates already-Merged finish dependencies. Current claim_next correctly requires dependency code to be reachable from the epic branch, but epic staleness maintenance is observation-only, so no executor or repair agent can make the required base reachable. Live reproduction: OOMPAH-459 is 26 commits behind main/5 ahead and all eight queued children wait on merged OOMPAH-475/467/464/466 ancestry; OOMPAH-460 is 34 behind and all six children wait behind OOMPAH-459. Scope: classify this as the existing synchronization policy's required-base condition; schedule one safe epic rebase/reconciliation action (never direct epic-to-epic sync), prevent duplicate repair dispatch, expose actionable queue/maintenance state, and resume integration after the repaired epic head is published. Preserve explicit finish-order and terminal-audit gates. Relevant files: oompah/orchestrator.py integration queue processing and epic synchronization policy, queue/API status summaries, and focused integration/staleness tests. Acceptance criteria: a Ready queue whose first task depends on merged code absent from its epic branch automatically enters a bounded repair path; after repair, eligible items are claimed in dependency order; no permanent attempts=0 queue remains; failures surface an actionable error without losing private heads; make test passes.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 21:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 21:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 21:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 12
- Tokens: 910.7K in / 4.3K out [915.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-562__20260729T211610Z.jsonl
---
author: oompah
created: 2026-07-29 21:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 21:18
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-29 21:19
---
**Understanding**: Epic integration deadlocks when a parent epic branch is stale (lacks merged code that its children depend on). The issue requires: (1) Detecting when a Ready queue's first task depends on merged code missing from its epic, (2) Scheduling a safe epic rebase/reconciliation, (3) Preventing duplicate repair dispatch, (4) Resuming integration after repair, (5) Preserving finish-order and terminal-audit gates.

**Planned approach**: 
1. Locate and understand the current claim_next logic and epic synchronization policy in orchestrator.py
2. Identify where the deadlock detection should occur
3. Implement a repair path that rebases the epic branch to incorporate merged dependencies
4. Add duplicate repair prevention
5. Expose actionable queue/maintenance state
6. Add tests for the repair workflow
7. Verify existing tests still pass
---
author: oompah
created: 2026-07-29 21:23
---
**Discovery**: Located relevant code:
- integration_queue.py: claim_next() selects next task with satisfied dependencies
- orchestrator.py: _process_integration_queues() coordinates queue processing
- orchestrator.py: _integration_satisfied_dependencies() checks dependency reachability
- orchestrator.py: _check_epic_staleness() detects stale branches (observation-only)
- orchestrator.py: _file_rebase_task() creates rebase sibling tasks

**Root cause**: claim_next() returns None when dependencies aren't satisfied, but no repair mechanism exists when dependencies are Done/Merged but unreachable from the epic branch. This causes permanent deadlock with attempts=0.

**Implementation plan**:
1. After claim_next() returns None in _process_integration_queues(), check if first ready item has unsatisfied dependencies that are terminal/merged
2. If so, file a rebase task to sync epic branch with merged dependencies
3. Track repair dispatch to prevent duplicates
4. Resume integration after rebase completes
---
author: oompah
created: 2026-07-29 21:28
---
Live diagnosis confirmed 14 Ready to Integrate entries are unleased at attempts=0 because required merged dependency code is absent from stale epic ancestry. OOMPAH-459 is 26 commits behind main/5 ahead; OOMPAH-460 is 34 behind and blocked behind OOMPAH-459. This task remains Backlog: promotion to Open was attempted and rejected because only a project owner may make it dispatchable. Owner action required: promote OOMPAH-562 to Open.
---
<!-- COMMENTS:END -->
