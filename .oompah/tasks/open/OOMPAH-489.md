---
id: OOMPAH-489
type: task
status: Open
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
updated_at: '2026-07-29T02:12:48.946840Z'
work_branch: epic-OOMPAH-460
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
oompah.agent_run_id: 1b7b0ffa-5654-425b-9961-e6fb1212e5c7
oompah.work_branch: epic-OOMPAH-460
oompah.task_costs:
  total_input_tokens: 908685
  total_output_tokens: 3909
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 908685
      output_tokens: 3909
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 908685
    output_tokens: 3909
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:12:46.721539+00:00'
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
<!-- COMMENTS:END -->
