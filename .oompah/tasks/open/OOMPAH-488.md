---
id: OOMPAH-488
type: task
status: Open
priority: 1
title: Validate the complete task Done-Merged-Archived audit lifecycle
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-476
- OOMPAH-477
- OOMPAH-479
- OOMPAH-481
- OOMPAH-484
- OOMPAH-485
- OOMPAH-486
- OOMPAH-487
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:27.238658Z'
updated_at: '2026-07-29T18:34:17.982033Z'
work_branch: epic-OOMPAH-460--task-OOMPAH-488
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3d3ae26df8c3bd62eb896f6ecfe8c0a0ea7b2cbe36c095fc3e808030a7029a2e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:10:59.016950+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed active OOMPAH-281 and OOMPAH-282 in full;\
    \ they cover CI runners and state-branch migration, respectively. Closest historical\
    \ tasks are OOMPAH-202 (release-delivery E2E) and OOMPAH-260 (state-branch E2E),\
    \ both terminal and distinct. Current terminal-audit coverage is component-level;\
    \ no active task covers the complete Done \u2192 Merged \u2192 Archived Git-fixture\
    \ lifecycle with independent auditors and failure/recovery variants."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: d6f5601e-997d-4175-8930-e6aa5fc7277b
oompah.work_branch: epic-OOMPAH-460--task-OOMPAH-488
oompah.task_costs:
  total_input_tokens: 763127
  total_output_tokens: 8252
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 677000
      output_tokens: 7292
      cost_usd: 0.0
    opus:
      input_tokens: 86127
      output_tokens: 960
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 396439
    output_tokens: 2988
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:10:59.015823+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 280561
    output_tokens: 4304
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:32:12.430732+00:00'
  - profile: deep
    model: opus
    input_tokens: 86127
    output_tokens: 960
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:34:14.579105+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-460--task-OOMPAH-488
  base_branch: epic-OOMPAH-460
  base_sha: b0ceda2643cbc37c166ac58bed9a9b6f3898b681
  updated_at: '2026-07-29T18:33:39.968207+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-488__20260729T183010Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: ci_fix
    source_branch: epic-OOMPAH-460--task-OOMPAH-488
    source_sha: b0ceda2643cbc37c166ac58bed9a9b6f3898b681
    completed_at: '2026-07-29T18:32:12.435604+00:00'
  - run_id: OOMPAH-488__20260729T183344Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: ci_fix
    source_branch: epic-OOMPAH-460--task-OOMPAH-488
    source_sha: b0ceda2643cbc37c166ac58bed9a9b6f3898b681
    completed_at: '2026-07-29T18:34:14.583336+00:00'
---
## Summary

Implementation scope

Create an end-to-end Git fixture and fake provider/SCM setup for one implementation task. Dispatch a worker with provider/model A, commit/push work, request Done, assert In Validation, dispatch provider/model B auditor, submit PASS, assert Done and review creation. Simulate correct review merge, assert a separate Merged audit with completion prerequisite, pass it, then age the task and pass a safe-retirement Archived audit. Assert durable comments/metadata, API summaries, metrics, state-branch commits, and restart recovery between at least two stages. Add failure variants for incomplete work, failed CI, wrong merge target, and unsafe archive.

Tests

This task is the test implementation. Keep fixtures deterministic and offline; do not call real providers or forges. Run the new test file repeatedly, relevant existing integration suites, and make test.

Acceptance criteria

The automated scenario proves three different auditors/contracts occur in order, the worker never self-certifies, each failure returns to the documented repair state, and state remains correct across restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:09
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 02:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:11
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 9
- Tokens: 396.4K in / 3.0K out [399.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 16s
- Log: OOMPAH-488__20260729T020947Z.jsonl
---
author: oompah
created: 2026-07-29 18:30
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 18:30
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 18:32
---
Agent completed successfully in 133s (284865 tokens)
---
author: oompah
created: 2026-07-29 18:32
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 18
- Tokens: 280.6K in / 4.3K out [284.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 13s
- Log: OOMPAH-488__20260729T183010Z.jsonl
---
author: oompah
created: 2026-07-29 18:32
---
Agent completed without closing this issue (133s (284865 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 18:33
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-29 18:33
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 18:34
---
Agent completed successfully in 41s (87087 tokens)
---
author: oompah
created: 2026-07-29 18:34
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 4
- Tokens: 86.1K in / 960 out [87.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 41s
- Log: OOMPAH-488__20260729T183344Z.jsonl
---
<!-- COMMENTS:END -->
