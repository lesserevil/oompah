---
id: OOMPAH-1267
type: task
status: In Progress
priority: null
title: Make restart replacement rollback test deterministic under concurrent gates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T08:43:25.263614Z'
updated_at: '2026-08-21T03:04:46.056472Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 74c46553-2c2b-43cf-a780-9f13e770c900
  request_fingerprint: c93c49f73d14f0dbd98db4eaf2f0bc6f44f4965a6f4e68ab29b4fa036d4eeecd
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d12a8b6a59aa90f19f4ddbe2f11d1a7a62462ddc8014f5351f2e7cbea8ac64b7
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T00:42:37.229601+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The closest semantically-related tasks are OOMPAH-1008\
    \ and OOMPAH-1077, both addressing determinism under concurrent load but in workflow_worker\
    \ subsystems and already merged. OOMPAH-1267 is unique to the restart replacement\
    \ API test surface and remains the only active task for this specific race condition.\n\
    # Duplicate Investigation Analysis\n\nI'm examining whether OOMPAH-1267 is a duplicate\
    \ of an existing active task by comparing it against the provided project task\
    \ corpus.\n\n## Analysis\n\n**OOMPAH-1267** describes a specific, persistent concurrency\
    \ bug in `tests/test_restart_api.py::test_replacement_timeout_rolls_back_before_concurrent_replacement`.\
    \ The issue is:\n- A test that passes in isolation but fails under concurrent\
    \ load from other unrelated quality gates\n- The root cause is load-sensitive\
    \ timing assumptions rather than deterministic synchronization\n- Requires replacing\
    \ wall-clock assumptions with explicit observable synchronization\n- Specific\
    \ to restart replacement lifecycle/locking code\n\n## Corpus Review\n\nI scanned\
    \ all 26 similar candidates in the project task corpus. The closest semantic matches\
    \ involve making tests deterministic under load:\n\n- **OOMPAH-1008** (Merged):\
    \ \"Make late-effect quarantine deterministic under full-suite load\" \u2014 fixes\
    \ `test_late_success_checkpoints_receipt_without_duplicate_apply` in workflow_worker\
    \ tests\n- **OOMPAH-1077** (Merged): \"Make workflow-worker heartbeat lease proof\
    \ deterministic under loaded CI\" \u2014 fixes test_heartbeat_renews_lease_during_long_effect\
    \ in workflow_worker tests\n\nHowever, these are:\n1. **Different test files**\
    \ (workflow_worker vs restart_api)\n2. **Different subsystems** (workflow scheduling\
    \ vs restart replacement)\n3. **All in terminal states** (Merged/Done/Archived),\
    \ making them completed historical context rather than active duplicates per the\
    \ screening rules\n\n## Verdict\n\nNo active duplicate found. While OOMPAH-1267\
    \ shares the general pattern of \"make load-sensitive tests deterministic,\" it\
    \ addresses a unique, unrelated test in a different subsystem (restart replacement)\
    \ that is currently Open.\n\n---\n\nFocus handoff: duplicate_detector\nDuplicate\
    \ preflight verdict: no_duplicate\nMatches: none\n\nEvidence: The closest semantically-related\
    \ tasks are OOMPAH-1008 and OOMPAH-1077, both addressing determinism under concurre"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: ab82df24-0bc5-4a87-b982-4ef5d62aeb96
oompah.work_contributors:
  runs:
  - run_id: 671f8f5990b64a229b74342ef73ff72e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
  - run_id: 671f8f5990b64a229b74342ef73ff72e--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
  - run_id: a64c1a38713847759e54088c9bd97c61--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
  - run_id: a64c1a38713847759e54088c9bd97c61--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1267
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-21T00:42:37.231947+00:00'
  - run_id: 3ab1fbcf2cb847568ec7fc081f843b00--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: test
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
  - run_id: 867dc057d5b643f4b5c17cea4cc8f9d6--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: test
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
  - run_id: e9af0cd1d42a4c3abccef2b1e3a774fc--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: test
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
  - run_id: 991f3b6ee8d645e4b9b7a7fea3cfef76--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: test
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
  - run_id: 3068b6736743423fa1e65355f407768d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: test
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2118
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2118
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2118
    cost_usd: 0.0
    recorded_at: '2026-08-21T00:42:37.228764+00:00'
---
## Summary

Repeated concurrency bug: tests/test_restart_api.py::test_replacement_timeout_rolls_back_before_concurrent_replacement failed late in two independent full Makefile gates running concurrently on OOMPAH-1266 and OOMPAH-1249. Both branches are unrelated to restart lifecycle code; the exact test passes isolated and the full restart API file passes 33/33, proving the current synchronization/timeout contract is load-sensitive rather than deterministic. Diagnose the replacement-timeout/concurrent-replacement ordering and replace wall-clock/test-runner-load assumptions with explicit observable synchronization or a bounded state predicate. Preserve the production guarantee that a timed-out replacement rolls back before a concurrent replacement can acquire authority. Relevant context: tests/test_restart_api.py and restart replacement lifecycle/locking code. Required tests: deterministic interleavings for timeout-before-replacement and replacement-before-timeout, repeated/parallel execution under CPU load, no leaked lifecycle state or process, and focused restart plus full Makefile gate. Acceptance: the exact race test cannot fail solely because another quality gate is consuming the box, real ordering regressions still fail, and no timeout is simply widened to hide the race.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 18s
- Log: OOMPAH-1267__20260820T231534Z.jsonl
---
author: oompah
created: 2026-08-21 00:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:41
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 00:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 41s
- Log: OOMPAH-1267__20260821T004126Z.jsonl
---
author: oompah
created: 2026-08-21 02:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 02:13
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-21 02:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 36s
- Log: OOMPAH-1267__20260821T021326Z.jsonl
---
author: oompah
created: 2026-08-21 02:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 02:34
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-21 02:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 9s
- Log: OOMPAH-1267__20260821T023452Z.jsonl
---
author: oompah
created: 2026-08-21 02:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 02:44
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-21 02:45
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 54s
- Log: OOMPAH-1267__20260821T024448Z.jsonl
---
author: oompah
created: 2026-08-21 02:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 02:54
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-21 02:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: OOMPAH-1267__20260821T025436Z.jsonl
---
author: oompah
created: 2026-08-21 03:02
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
