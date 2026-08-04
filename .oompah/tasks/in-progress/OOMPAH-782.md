---
id: OOMPAH-782
type: feature
status: In Progress
priority: 1
title: Cut review and CI reconciliation over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:00.734500Z'
updated_at: '2026-08-04T20:28:46.495089Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-782
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4d7be90effcf4eb44b89bc2e71d5b6a5bed23ea571f0690ffd8d2643f8526655
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:23:40.534729+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active task duplicates review/CI reconciliation. OOMPAH-768\
    \ is the parent epic; OOMPAH-781, OOMPAH-791, and OOMPAH-793 cover distinct sibling\
    \ domains, while OOMPAH-804 covers runtime wiring. Historical terminal tasks were\
    \ excluded.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: No active task duplicates review/CI\
    \ reconciliation. OOMPAH-768 is the parent epic; OOMPAH-781, OOMPAH-791, and OOMPAH-793\
    \ cover distinct sibling domains, while OOMPAH-804 covers runtime wiring. Historical\
    \ terminal tasks were excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1b1016c3-ad4d-4954-b0f3-016e8bbeb5a7
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-782
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-782
  base_branch: epic-OOMPAH-768
  base_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
  updated_at: '2026-08-04T20:28:41.283462+00:00'
oompah.task_costs:
  total_input_tokens: 46834
  total_output_tokens: 334
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46834
      output_tokens: 334
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46834
    output_tokens: 334
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:23:40.527207+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-782__20260804T202310Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-782
    source_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
    completed_at: '2026-08-04T20:23:40.553972+00:00'
---
## Summary

Migrate In Review and repair progression to unified review/CI/Git facts and durable observation/action jobs. Normalize open, draft, merged, closed-unmerged, missing PR, deleted source, changed head, capacity, CI pending/failing/passing, conflicts, and merge target. Use LandingFact for completion and TaskTransitionService for repair/terminal transitions. Required tests: provider timeout versus empty result, branch deletion after merge, head changes after recorded merge, capacity release/restart, CI registration delay, conflict repair, GitLab/GitHub parity, and UI reason parity. Acceptance: every In Review task has one durable owner/reassessment and naturally reaches merged, repair, retry, or actionable escalation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 20:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.8K in / 334 out [47.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 53s
- Log: OOMPAH-782__20260804T202310Z.jsonl
---
author: oompah
created: 2026-08-04 20:28
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 20:28
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
