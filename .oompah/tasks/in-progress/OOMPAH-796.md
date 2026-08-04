---
id: OOMPAH-796
type: feature
status: In Progress
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
updated_at: '2026-08-04T21:53:22.649460Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-04T21:25:30.768038+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-770 is the containing epic, while OOMPAH-768,\
    \ OOMPAH-784, OOMPAH-795, and OOMPAH-797 cover migration, metrics, projections,\
    \ and soak qualification respectively. No separate active task duplicates this\
    \ controller implementation.\nFocus handoff: duplicate_detector  \nDuplicate preflight\
    \ verdict: no_duplicate  \nMatches: none  \n\nEvidence: OOMPAH-770 is the containing\
    \ epic, while OOMPAH-768, OOMPAH-784, OOMPAH-795, and OOMPAH-797 cover migration,\
    \ metrics, projections, and soak qualification respectively. No separate active\
    \ task duplicates this controller implementation."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: efb6bde6-d645-45f9-b066-72582823b0bf
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-796
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-796
  base_branch: epic-OOMPAH-770
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-04T21:52:37.455778+00:00'
oompah.task_costs:
  total_input_tokens: 46262
  total_output_tokens: 499
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46262
      output_tokens: 499
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 45988
    output_tokens: 418
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:25:30.756760+00:00'
  - profile: default
    model: haiku
    input_tokens: 274
    output_tokens: 81
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:41:57.917530+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-796__20260804T212503Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-770--task-OOMPAH-796
    source_sha: a681ec2fc005f339063b3b8e2a139b8ae0b3c379
    completed_at: '2026-08-04T21:25:30.786143+00:00'
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
author: oompah
created: 2026-08-04 21:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 21:31
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 21:41
---
Branch-topology repair: the empty implementation run was dispatched from task/parent branch a681ec2fc, which predates completed hard-start prerequisites OOMPAH-765/766/785 on epic-OOMPAH-763 f1e7925b7. No task edits or commits exist. Returning to Open revokes the stale-base run; epic-OOMPAH-770 and this task branch will be fast-forwarded to the prerequisite lineage before redispatch.
---
author: oompah
created: 2026-08-04 21:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 33, Tool calls: 22
- Tokens: 274 in / 81 out [355 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 48s
- Log: OOMPAH-796__20260804T213133Z.jsonl
---
author: oompah
created: 2026-08-04 21:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 21:52
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 21:53
---
Understanding: I will trace WorkDecision evaluation, dispatch, recovery jobs, and bounded full-sync paths; implement a single totality/liveness controller that assigns exactly one allowed disposition and enqueues reason-coded remediation; then add focused regression coverage for stalls, graph impossibility, restart convergence, and idempotency.
---
<!-- COMMENTS:END -->
