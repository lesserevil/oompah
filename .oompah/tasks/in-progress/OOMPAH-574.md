---
id: OOMPAH-574
type: task
status: In Progress
priority: null
title: Rerun failed cached quality gates on explicit same-head retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:15:22.112289Z'
updated_at: '2026-07-30T13:32:54.265178Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f55f5eab566970505d6992f30c8a2400036ebbf0fd17826d3c17d85fb6db4782
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T13:32:44.977622+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Active tasks contain no matching behavior. Closest\
    \ reviewed tasks\u2014OOMPAH-38, OOMPAH-237, and OOMPAH-251\u2014cover release\
    \ gates or Release Delivery caching, not same-head BranchQualityGate retries."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 10443186-317f-4a96-91b0-b8d74abb4140
oompah.task_costs:
  total_input_tokens: 467950
  total_output_tokens: 3978
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 467950
      output_tokens: 3978
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 467950
    output_tokens: 3978
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:32:44.976653+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-574__20260730T133111Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-574
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T13:32:44.985927+00:00'
---
## Summary

Implementation scope

Make explicit integration resubmission invalidate and re-execute cached BranchQualityGate outcomes whose prior result is failed, timed_out, or error, even when the pushed head SHA is unchanged. Continue reusing passed evidence for the exact head, keep interrupted runs non-persistent, and prevent duplicate concurrent gates for one row/head. Wire the retry intent through the task handoff/API and integration executor without weakening normal cache reuse. Relevant files: oompah/quality_gate.py, oompah/integration_queue.py, oompah/server.py, and oompah/integration_executor.py.

Tests

Add regression coverage in tests/test_quality_gate.py, tests/test_integration_queue.py, and task-handoff/integration-executor tests for explicit same-SHA retry after failure, timeout, and error; passed-result reuse; interruption behavior; and concurrent retry deduplication. Run focused tests and the configured full Makefile gate.

Acceptance criteria

An explicit retry of an unchanged blocked integration row performs a real fresh quality gate instead of immediately reusing failed evidence; successful evidence remains safely reusable and no duplicate active gate is started.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 13:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 13:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 13:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 467.9K in / 4.0K out [471.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 41s
- Log: OOMPAH-574__20260730T133111Z.jsonl
---
author: oompah
created: 2026-07-30 13:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 13:32
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
