---
id: OOMPAH-603
type: feature
status: In Progress
priority: 2
title: Define and enforce repository hygiene health thresholds
parent: OOMPAH-588
children: []
blocked_by:
- OOMPAH-600
- OOMPAH-601
- OOMPAH-602
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:16:03.538398Z'
updated_at: '2026-07-30T16:33:41.938578Z'
work_branch: epic-OOMPAH-588--task-OOMPAH-603
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 011f90700a51d70bffc65436c95b7ee557a31fc8aef83e8b4a190a4052525e42
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T16:31:48.120010+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed active OOMPAH-281 and OOMPAH-282, plus historical\
    \ OOMPAH-10, OOMPAH-254, OOMPAH-256, and OOMPAH-260. They cover CI runners, state-branch\
    \ migration, tracker routing, or sync failures\u2014not repository-hygiene thresholds\
    \ and safe-prunable artifact health."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 026c8411-9861-4b04-9e90-a96b31df962b
oompah.work_branch: epic-OOMPAH-588--task-OOMPAH-603
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-588--task-OOMPAH-603
  base_branch: epic-OOMPAH-588
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T16:31:59.790742+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-603__20260730T160448Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-588--task-OOMPAH-603
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T16:08:42.204644+00:00'
  - run_id: OOMPAH-603__20260730T161605Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-588--task-OOMPAH-603
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T16:31:48.127593+00:00'
oompah.task_costs:
  total_input_tokens: 6928962
  total_output_tokens: 27562
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 6928962
      output_tokens: 27562
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 627394
    output_tokens: 2871
    cost_usd: 0.0
    recorded_at: '2026-07-30T16:08:42.195397+00:00'
  - profile: default
    model: haiku
    input_tokens: 6301568
    output_tokens: 24691
    cost_usd: 0.0
    recorded_at: '2026-07-30T16:31:48.118775+00:00'
---
## Summary

Implementation scope

Turn cleanup inventory into actionable health rather than raw counts. Report registered worktrees and local/remote branches by active, dirty, unmerged, terminal-protected, shared-owner, and safely-prunable categories; define configurable age/count thresholds in .env/.env.example; alert only on overdue safely-prunable artifacts or cleanup errors. Provide an operator verification path in docs/. Relevant files include maintenance status/state APIs, cleanup scheduler, dashboard/operator docs, and configuration.

Tests

Cover healthy protected inventory, overdue safe artifacts, dirty/unmerged preservation, threshold configuration, cleanup success/alert clear, restart persistence, and dashboard/API rendering. Run focused health/UI tests and make test.

Acceptance criteria

Operators can distinguish necessary retained work from hygiene debt, green status is based on zero overdue safe artifacts/errors rather than an unrealistic zero-branch count, and alerts clear after safe cleanup.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 16:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 16:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 16:08
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 627.4K in / 2.9K out [630.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 0s
- Log: OOMPAH-603__20260730T160448Z.jsonl
---
author: oompah
created: 2026-07-30 16:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 16:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 16:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 2, Tool calls: 52
- Tokens: 6.3M in / 24.7K out [6.3M total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 51s
- Log: OOMPAH-603__20260730T161605Z.jsonl
---
author: oompah
created: 2026-07-30 16:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 16:32
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 16:32
---
UNDERSTANDING: This issue requires defining health thresholds for repository hygiene. The scope is to:

1. Transform raw cleanup inventory into actionable health metrics (categorize worktrees/branches as active, dirty, unmerged, terminal-protected, shared-owner, safely-prunable)
2. Add configurable age/count thresholds to .env/.env.example
3. Alert only on overdue safely-prunable artifacts or cleanup errors
4. Update docs with operator verification path

This is an API/health feature, so I need to:
1. Find/create maintenance status APIs that report health categorized by artifact state
2. Find the cleanup scheduler and integrate threshold-based alerting
3. Add .env configuration for thresholds
4. Document operator verification procedures
5. Ensure dashboard/API properly render health status

As an Auth/Http specialist, I'll focus on API design, state transitions, configuration validation, and integration point definitions.

Let me explore the existing codebase structure.
---
author: oompah
created: 2026-07-30 16:33
---
DISCOVERY: Found existing cleanup infrastructure in orchestrator.py:
- MaintenanceJobState tracks scheduling state
- _cleanup_terminal_worktrees() removes MERGED/ARCHIVED worktrees
- _do_cleanup_worktrees() with batch limits and error tracking
- _maintenance_status exposed in get_snapshot() for dashboard

Current state: cleanup is binary (removed or not), not categorized by health.

Need to implement:
1. New repo_hygiene.py module for health categorization
2. .env configuration for thresholds
3. Integration into maintenance_status to expose health
4. Documentation for operators

Starting implementation now.
---
<!-- COMMENTS:END -->
