---
id: OOMPAH-482
type: feature
status: Open
priority: 1
title: Dispatch one repair-planner run for an epic that fails audit
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-466
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:30.191340Z'
updated_at: '2026-07-29T18:36:57.431242Z'
work_branch: epic-OOMPAH-459--task-OOMPAH-482
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5d34fedffb4ff803f6dd76be8a7be0f8fd5e1cd2d329a1c465f5281c87f7db5b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:00:16.747093+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed active tasks OOMPAH-281 and OOMPAH-282 in\
    \ full; neither covers epic audit repair planning. Historical OOMPAH-271 and OOMPAH-275\u2013\
    280 concern epic rebases and are terminal, so they are excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 7be8778b-9663-4db8-8135-ef23067bee34
oompah.work_branch: epic-OOMPAH-459--task-OOMPAH-482
oompah.task_costs:
  total_input_tokens: 406406
  total_output_tokens: 2725
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 406406
      output_tokens: 2725
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 285362
    output_tokens: 1668
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:00:16.746610+00:00'
  - profile: default
    model: haiku
    input_tokens: 121044
    output_tokens: 1057
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:34:18.431433+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-459--task-OOMPAH-482
  base_branch: epic-OOMPAH-459
  base_sha: 65c8e4725fe931bf0fa9c3357d153ba003ad03c4
  updated_at: '2026-07-29T18:33:35.425775+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-482__20260729T183344Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: chore
    source_branch: epic-OOMPAH-459--task-OOMPAH-482
    source_sha: 65c8e4725fe931bf0fa9c3357d153ba003ad03c4
    completed_at: '2026-07-29T18:34:18.463802+00:00'
---
## Summary

Implementation scope

When coordinator result handling reopens an epic as Open with audit:repair-needed, allow _plan_open_epics/_should_dispatch_epic to schedule one epic_planner run even though children already exist. Provide the failed audit summary and evidence references in the prompt. Update the epic_planner focus for repair mode: inspect existing children, reopen the child responsible for a gap or create narrowly scoped missing children, add dependencies, then remove audit:repair-needed and end without implementing code. Prevent duplicate repair runs with persisted audit ID/claim metadata. Ordinary already-planned epics without the label remain nondispatchable.

Tests

Cover existing child reopened, missing child created, multiple findings, dependency creation, no duplicate planning, restart, label removal, planner failure/retry, normal epic unchanged, and nested epic repair. Run epic planning tests and make test.

Acceptance criteria

A failed epic audit becomes actionable without the auditor creating work; exactly one repair-planner session reconciles the findings into normal child workflow.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:00
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 7
- Tokens: 285.4K in / 1.7K out [287.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 47s
- Log: OOMPAH-482__20260729T015933Z.jsonl
---
author: oompah
created: 2026-07-29 18:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:33
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-29 18:34
---
Agent completed successfully in 49s (122101 tokens)
---
author: oompah
created: 2026-07-29 18:34
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 121.0K in / 1.1K out [122.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-482__20260729T183344Z.jsonl
---
author: oompah
created: 2026-07-29 18:34
---
Agent completed without closing this issue (49s (122101 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
