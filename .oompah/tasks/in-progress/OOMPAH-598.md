---
id: OOMPAH-598
type: bug
status: In Progress
priority: 1
title: Detect and deliver standalone Ready to Integrate tasks without PRs
parent: OOMPAH-587
children: []
blocked_by:
- OOMPAH-593
start_blocked_by: &id001 []
labels: []
assignee: null
created_at: '2026-07-30T14:15:29.695490Z'
updated_at: '2026-07-30T15:42:39.659006Z'
work_branch: epic-OOMPAH-587--task-OOMPAH-598
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 804c0cd117349b00c1fad257b2fb304f290d07ececee26378ec020331156ebe8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T15:40:21.951300+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Reviewed active tasks OOMPAH-587, OOMPAH-593,\
    \ OOMPAH-596, OOMPAH-597, OOMPAH-599, and OOMPAH-600 plus the four stranded Ready\
    \ tasks. They cover the parent epic, auth verification, conflict repair, ordered\
    \ epic integration, final auditing, and post-delivery cleanup\u2014not standalone\
    \ Ready-to-Integrate reconciliation. Terminal tasks were excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 254adbea-a1a2-47d2-9313-917b08a98287
oompah.work_branch: epic-OOMPAH-587--task-OOMPAH-598
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-587--task-OOMPAH-598
  base_branch: epic-OOMPAH-587
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:41:10.283180+00:00'
oompah.task_costs:
  total_input_tokens: 1164277
  total_output_tokens: 6308
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1164277
      output_tokens: 6308
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1164277
    output_tokens: 6308
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:40:21.949609+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-598__20260730T153653Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-587--task-OOMPAH-598
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:40:21.961176+00:00'
---
## Summary

Implementation scope

Add reconciliation for standalone tasks whose tracker state is Ready to Integrate and whose branch is pushed, but which have neither an active integration execution nor an open PR. Select the configured delivery mechanism deterministically, enqueue/open it idempotently, and alert on genuinely undeliverable rows. Recover the current OOMPAH-574, OOMPAH-575, OOMPAH-576, and OOMPAH-581 rows. Do not create duplicate PRs or bypass the configured full gate. Relevant areas include landing reconciliation, integration queue, review creation, webhook state, and release-delivery status.

Tests

Cover pushed standalone branch, missing branch, existing open/closed PR, existing queue row, duplicate ticks, restart, gate failure/retry, and successful merge/audit. Run focused tests and make test.

Acceptance criteria

A pushed standalone Ready task cannot remain invisible with no PR/queue activity beyond the reconciliation interval; all four current rows obtain a valid delivery path or explicit actionable failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:17
---
Coordination: OOMPAH-593 exclusively owns delivery/live verification of OOMPAH-575. After OOMPAH-593 completes, this task owns stranded-ready reconciliation and delivery for OOMPAH-574, OOMPAH-576, and OOMPAH-581 plus the generic watchdog fix; do not duplicate OOMPAH-575 work.
---
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 15:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 28
- Tokens: 1.2M in / 6.3K out [1.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 42s
- Log: OOMPAH-598__20260730T153653Z.jsonl
---
author: oompah
created: 2026-07-30 15:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:41
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 15:42
---
**UNDERSTANDING & PLAN**

Issue: Standalone tasks in 'Ready to Integrate' state with pushed branches are not being delivered (no PR/queue activity). Need to detect and deliver them deterministically without creating duplicates.

Scope: Focus on stranded-ready reconciliation for OOMPAH-574, OOMPAH-576, OOMPAH-581 (OOMPAH-575 is owned by OOMPAH-593). Note: Duplicate screening ran previously, so OOMPAH-598 task itself should be singleton-checked.

Planned approach:
1. Explore codebase to find landing/integration reconciliation code
2. Identify delivery mechanisms (PR creation, integration queue)
3. Locate relevant tracker state checks and branch validation
4. Implement idempotent reconciliation loop for stranded-ready tasks
5. Add delivery path selection (deterministic, respects config)
6. Cover test scenarios: pushed branch, missing branch, existing PR (open/closed), existing queue row, duplicates, restarts
7. Verify all four rows obtain valid delivery path or actionable failure

Starting code exploration now.
---
<!-- COMMENTS:END -->
