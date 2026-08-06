---
id: OOMPAH-847
type: bug
status: Open
priority: 1
title: Isolate dispatch-lock and epic-review unit tests from unrelated loaded-gate
  work
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:13:46.553414Z'
updated_at: '2026-08-06T04:18:35.172497Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-847
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 68036329739824bfaec7327f341fe5fc959ec48183a5d46321f7235245b9fcd7
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T04:18:26.063251+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-846 addresses universal validation-resource lease\
    \ enforcement, while OOMPAH-831 addresses auditor inspection tooling; neither\
    \ covers isolating these two unit tests. Closest terminal task OOMPAH-814 is excluded.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: OOMPAH-846 addresses universal validation-resource\
    \ lease enforcement, while OOMPAH-831 addresses auditor inspection tooling; neither\
    \ covers isolating these two unit tests. Closest terminal task OOMPAH-814 is excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3ff29d92-79da-4d83-a732-8b1b63a9ac0a
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-847
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-847
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T04:15:20.363018+00:00'
oompah.task_costs:
  total_input_tokens: 45935
  total_output_tokens: 400
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 45935
      output_tokens: 400
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 45935
    output_tokens: 400
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:18:26.058304+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-847__20260806T041558Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-847
    source_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
    completed_at: '2026-08-06T04:18:26.074882+00:00'
---
## Summary

The OOMPAH-831 exact combined-tree gate at head 93b0295bc passed 16,085 tests and then failed tests/test_dispatch_lane_contract.py::TestDispatchLockExceptionSafety::test_second_dispatch_succeeds_after_first_raises and tests/test_epic_strategy.py::TestOpenEpicMainPrs::test_existing_pr_waits_for_changed_head_quality_gate during a 1,041-second saturated run. Neither test exercises OOMPAH-831 auditor code. The dispatch-lock test lets the second call traverse unrelated audit/duplicate-preflight scheduling; the epic-review test persists an unasserted review-capacity adoption before checking its mocked gate result. Concurrent worker commands were also proven to bypass OOMPAH-816 resource leasing (tracked separately in OOMPAH-846). Implementation scope: obtain exact failure classification with isolated and loaded reproductions; remove unrelated real tracker/store/executor/network/background work from both unit tests while keeping production semantics and assertions strict; add deterministic cleanup for any owned executor/store/event-loop resources; use a scoped bounded timeout only if the intended operation itself legitimately needs loaded-gate headroom. Do not raise the global timeout or mask semantic failures. Required tests: both exact nodes repeated concurrently; complete dispatch-lane and epic-strategy modules; an ordering/leakage sequence that proves no background work crosses tests; canonical make test at the review head. Acceptance: both tests assert only lock exception safety or changed-head gate behavior, fail when that contract regresses, exit with no live background work, and pass reliably in a saturated exact gate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:15
---
In-flight workaround prepared on claimed OOMPAH-831 (not yet tested/committed while OOMPAH-791 owns the validation lane): replace the dispatch-lock test full scheduler traversal with an AsyncMock of _handle_dispatch_needed_locked that raises then returns, asserting two awaits and real outer-lock release; mock/assert _adopt_open_review_capacity in the changed-head epic test so it does not perform unrelated SQLite I/O. The systemic task should independently verify exact failure classification, loaded repetitions, cleanup, and any adjacent cases rather than duplicate these two lines blindly. OOMPAH-846 separately owns universal lease-bypass prevention.
---
author: oompah
created: 2026-08-06 04:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 04:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 45.9K in / 400 out [46.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 15s
- Log: OOMPAH-847__20260806T041558Z.jsonl
---
<!-- COMMENTS:END -->
