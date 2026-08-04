---
id: OOMPAH-796
type: feature
status: Open
priority: 1
title: Implement the universal totality and liveness controller
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:26.773150Z'
updated_at: '2026-08-04T21:25:33.427296Z'
work_branch: epic-OOMPAH-770--task-OOMPAH-796
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8bb2e964b0f1cc4d860a880a78e3c62b765dd8cb72b5bcbd2122c63d9151e7af
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 49618050-e93c-4624-b9f3-e6ff32537916
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T21:24:06.939863+00:00'
  claim_expires_at: '2026-08-04T21:54:06.939863+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 87fb254d-1526-4841-a9c7-b10b0805010f
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-796
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-796
  base_branch: epic-OOMPAH-770
  base_sha: a681ec2fc005f339063b3b8e2a139b8ae0b3c379
  updated_at: '2026-08-04T21:24:43.812720+00:00'
oompah.task_costs:
  total_input_tokens: 45988
  total_output_tokens: 418
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 45988
      output_tokens: 418
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 45988
    output_tokens: 418
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:25:30.756760+00:00'
---
## Summary

Build a controller that evaluates every nonterminal WorkDecision on relevant events and bounded full-sync. Enforce exactly one disposition: runnable, durably owned, named-prerequisite blocked, retry-scheduled, or action_required. Detect missing/conflicting/expired/impossible ownership, overdue reassessment, exhausted recovery, and graph impossibility. Enqueue reason-coded recovery jobs instead of writing status; deduplicate/escalate only when automatic recovery is unavailable. Required tests: totality across statuses, duplicate owners, missing queue/audit/review job, expired lease, stale facts, retry due/exhausted, dependency cycles, restart convergence, and idempotent remediation. Acceptance: no unknown nonterminal disposition survives one full-sync interval and every synthetic stall recovers or escalates with concrete evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Hard-start prerequisite OOMPAH-785 is Done. Promoting the universal totality/liveness controller for server dispatch as the first OOMPAH-770 implementation wave.
---
author: oompah
created: 2026-08-04 21:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 21:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.0K in / 418 out [46.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 56s
- Log: OOMPAH-796__20260804T212503Z.jsonl
---
<!-- COMMENTS:END -->
