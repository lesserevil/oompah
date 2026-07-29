---
id: OOMPAH-489
type: task
status: In Progress
priority: 1
title: Validate nested epic auditing, repair planning, races, and cross-tracker behavior
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-452
- OOMPAH-478
- OOMPAH-482
- OOMPAH-483
- OOMPAH-488
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:28.198709Z'
updated_at: '2026-07-29T19:17:53.449811Z'
work_branch: epic-OOMPAH-460--task-OOMPAH-489
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 137a6659244ebf2cdf5ed431ad6a7036da455e897c7eba21d8f9304442b9dc6f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:12:46.722550+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: No active duplicate found. The closest reviewed tasks are terminal OOMPAH-165
    (nested/shared epic rollup), OOMPAH-168 (shared epic orchestration), and OOMPAH-219
    (shared-worktree race reconciliation); their scopes differ. The only nonterminal
    records, OOMPAH-281 and OOMPAH-282, are unrelated.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8a79fe1a-5014-4660-a3c0-54f4d4bcb1cb
oompah.work_branch: epic-OOMPAH-460--task-OOMPAH-489
oompah.task_costs:
  total_input_tokens: 1976956
  total_output_tokens: 15957
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1927004
      output_tokens: 15591
      cost_usd: 0.0
    sonnet:
      input_tokens: 49952
      output_tokens: 366
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 908685
    output_tokens: 3909
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:12:46.721539+00:00'
  - profile: default
    model: haiku
    input_tokens: 1018319
    output_tokens: 11682
    cost_usd: 0.0
    recorded_at: '2026-07-29T19:16:16.012268+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 49952
    output_tokens: 366
    cost_usd: 0.0
    recorded_at: '2026-07-29T19:17:08.033429+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-460--task-OOMPAH-489
  base_branch: epic-OOMPAH-460
  base_sha: b0ceda2643cbc37c166ac58bed9a9b6f3898b681
  updated_at: '2026-07-29T19:17:51.499166+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-489__20260729T184610Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: epic-OOMPAH-460--task-OOMPAH-489
    source_sha: ea5f0f0a9a5ead2ca542f17afb038973c5e4727b
    completed_at: '2026-07-29T19:16:16.016743+00:00'
  - run_id: OOMPAH-489__20260729T191645Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: general
    source_branch: epic-OOMPAH-460--task-OOMPAH-489
    source_sha: ea5f0f0a9a5ead2ca542f17afb038973c5e4727b
    completed_at: '2026-07-29T19:17:08.038667+00:00'
---
## Summary

Implementation scope

Add end-to-end scenarios for a shared epic with several child contributors/models and a nested child epic. Prove the epic auditor excludes every contributing model, child In Validation blocks rollup, Done and Merged audits use the correct branch chain, and a failed epic audit reopens with audit:repair-needed for exactly one repair-planner run. Add races: evidence changes during audit, duplicate webhook plus polling merge signals, service restart with a running audit, no independent candidate, and authorized owner override. Run the same lifecycle contract against native Markdown and GitHub tracker fixtures, plus GitLab when its recovered adapter is present.

Tests

This task is the test implementation. Use deterministic clocks, fake providers, bare Git remotes, and fake SCM APIs; no external network. Run focused tests and make test.

Acceptance criteria

Nested/shared epic work cannot terminalize early, stale or duplicate results cannot win races, repair planning is idempotent, independence is enforced across contributors, and tracker adapters share the same externally visible lifecycle.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:11
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:12
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 16
- Tokens: 908.7K in / 3.9K out [912.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 40s
- Log: OOMPAH-489__20260729T021111Z.jsonl
---
author: oompah
created: 2026-07-29 18:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:46
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 19:16
---
Agent completed successfully in 1818s (1030001 tokens)
---
author: oompah
created: 2026-07-29 19:16
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 2, Tool calls: 163
- Tokens: 1.0M in / 11.7K out [1.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 30m 18s
- Log: OOMPAH-489__20260729T184610Z.jsonl
---
author: oompah
created: 2026-07-29 19:16
---
Agent completed without closing this issue (1818s (1030001 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 19:16
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 19:16
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 19:17
---
Agent completed successfully in 29s (50318 tokens)
---
author: oompah
created: 2026-07-29 19:17
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 1
- Tokens: 50.0K in / 366 out [50.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 29s
- Log: OOMPAH-489__20260729T191645Z.jsonl
---
author: oompah
created: 2026-07-29 19:17
---
Agent completed without closing this issue (29s (50318 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-29 19:17
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-29 19:17
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
