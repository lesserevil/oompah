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
updated_at: '2026-07-29T02:11:01.193003Z'
work_branch: epic-OOMPAH-460
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
oompah.agent_run_id: be6c7c61-0e0f-43d8-84fd-284d420fac05
oompah.work_branch: epic-OOMPAH-460
oompah.task_costs:
  total_input_tokens: 396439
  total_output_tokens: 2988
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 396439
      output_tokens: 2988
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 396439
    output_tokens: 2988
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:10:59.015823+00:00'
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
<!-- COMMENTS:END -->
