---
id: OOMPAH-596
type: bug
status: In Progress
priority: 1
title: Rearm conflict repairs after recoverable agent infrastructure failure
parent: OOMPAH-587
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:15:26.248587Z'
updated_at: '2026-07-30T15:44:02.209051Z'
work_branch: epic-OOMPAH-587--task-OOMPAH-596
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b8c9779d72e8d10e89d53ba9eed3f6602095a5255ac360e48817df156b151940
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T15:32:14.421445+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive investigation, I can now provide my findings:


    ## Duplicate Investigation Results


    I have thoroughly searched the task system across all states (open, backlog, merged,
    archived) for tasks related to:

    - Conflict repair and rebase-conflict recovery

    - Recoverable infrastructure failures (task-auth, provider, sandbox)

    - Repair worker lifecycle and retry logic

    - Orchestrator landing/retry logic

    - Watchdog state management

    - Queue API/UI for integration repairs

    - Tasks OOMPAH-484, OOMPAH-487, OOMPAH-587, OOMPAH-597, OOMPAH-598, OOMPAH-599


    **Search Results:**

    1. **No tasks** exist matching "conflict repair," "infrastructure failure recovery,"
    or "rearm" patterns

    2. **No tasks** in the 400s, 500s, or 600s numbering range exist as files (highest
    is OOMPAH-282)

    3. **No documentation** in docs/ or plans/ covers conflict repair lifecycle management

    4. **No related code patterns** for conflict repair recovery in the codebase

    5. **Closest reviewed task:** OOMPAH-281 (self-hosted GitHub Actions runner) -
    completely unrelated topic


    **Context from task metadata:**

    - OOMPAH-596 is part of epic OOMPAH-587 with siblings OOMPAH-597, OOMPAH-598,
    OOMPAH-599

    - Referenced predecessor tasks (OOMPAH-484, OOMPAH-487) don''t exist as files,
    indicating forward-planned work

    - This is the first task in a coordinated epic addressing conflict repair infrastructure


    **Evidence:** This is a brand-new feature/fix addressing a previously unhandled
    scenario (conflict repair failure recovery). The lack of any existing tasks covering
    this topic, combined with its position as an epic with planned sibling tasks,
    conclusively indicates this is original work, not a duplicate.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Comprehensive search of all task states (.oompah/tasks/{open,backlog,merged,archived}),
    docs, and plans found zero existing tasks or documentation addressing conflict
    repair recovery after recoverable inf'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 01e8b0b6-f4ed-4161-930e-1da63a291a43
oompah.work_branch: epic-OOMPAH-587--task-OOMPAH-596
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-587--task-OOMPAH-596
  base_branch: epic-OOMPAH-587
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:40:36.349788+00:00'
oompah.task_costs:
  total_input_tokens: 160074
  total_output_tokens: 7442
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 101874
      output_tokens: 6612
      cost_usd: 0.0
    opus:
      input_tokens: 58200
      output_tokens: 830
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 138
    output_tokens: 4870
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:32:14.419884+00:00'
  - profile: default
    model: haiku
    input_tokens: 53373
    output_tokens: 1034
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:33:18.378030+00:00'
  - profile: deep
    model: opus
    input_tokens: 58200
    output_tokens: 830
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:34:21.864357+00:00'
  - profile: default
    model: haiku
    input_tokens: 48363
    output_tokens: 708
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:36:03.189018+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-596__20260730T153052Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-587--task-OOMPAH-596
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:32:14.425457+00:00'
  - run_id: OOMPAH-596__20260730T153246Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: frontend
    source_branch: epic-OOMPAH-587--task-OOMPAH-596
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:33:18.386183+00:00'
  - run_id: OOMPAH-596__20260730T153357Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: frontend
    source_branch: epic-OOMPAH-587--task-OOMPAH-596
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:34:21.867901+00:00'
  - run_id: OOMPAH-596__20260730T153442Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: frontend
    source_branch: epic-OOMPAH-587--task-OOMPAH-596
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:36:03.195888+00:00'
---
## Summary

Implementation scope

Fix integration repair lifecycle so a rebase-conflict row is not left permanently blocked when its repair worker exits because of task-auth, provider, sandbox, or other recoverable infrastructure failure. Preserve the real conflict and attempt history, retry only after the prerequisite health condition changes or bounded backoff expires, and transition exhausted repairs to an explicit needs-human state with exact safe instructions. Apply the recovery path to OOMPAH-484 and OOMPAH-487 after scoped task auth is live. Relevant files include integration queue/executor repair dispatch, orchestrator landing/retry logic, watchdog state, and queue API/UI summaries.

Tests

Cover real conflict plus 401, provider failure, successful retry, repeated failure/backoff, restart, no duplicate workers, and needs-human exhaustion. Run focused integration/orchestrator tests and make test.

Acceptance criteria

Recoverable infrastructure failure cannot silently strand a conflict row; OOMPAH-484 and OOMPAH-487 either integrate after repair or show an explicit unresolved conflict requiring a named operator action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 15:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 47, Tool calls: 25
- Tokens: 138 in / 4.9K out [5.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 29s
- Log: OOMPAH-596__20260730T153052Z.jsonl
---
author: oompah
created: 2026-07-30 15:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:32
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:33
---
Agent completed successfully in 51s (54407 tokens)
---
author: oompah
created: 2026-07-30 15:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 4
- Tokens: 53.4K in / 1.0K out [54.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 51s
- Log: OOMPAH-596__20260730T153246Z.jsonl
---
author: oompah
created: 2026-07-30 15:33
---
Agent completed without closing this issue (51s (54407 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 15:33
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-30 15:33
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:34
---
Agent completed successfully in 35s (59030 tokens)
---
author: oompah
created: 2026-07-30 15:34
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 5
- Tokens: 58.2K in / 830 out [59.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 35s
- Log: OOMPAH-596__20260730T153357Z.jsonl
---
author: oompah
created: 2026-07-30 15:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:34
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:36
---
Agent completed successfully in 87s (49071 tokens)
---
author: oompah
created: 2026-07-30 15:36
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 48.4K in / 708 out [49.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 27s
- Log: OOMPAH-596__20260730T153442Z.jsonl
---
author: oompah
created: 2026-07-30 15:36
---
Agent completed 3 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: oompah
created: 2026-07-30 15:40
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #11)

**State audited:** `Needs Human`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Last agent comment signals completion without a human question; the Needs Human transition appears accidental.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-07-30 15:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:40
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 15:43
---
UNDERSTANDING: The issue is about the integration repair lifecycle for rebase conflicts. Currently, when execute_integration() detects a conflict (status='conflict'), the integration queue marks it as 'blocked' permanently. If a repair worker exits due to recoverable infrastructure failure (task-auth 401, provider failure, sandbox issues), the conflict row stays blocked indefinitely.

Key findings:
1. integration_executor.py returns status='conflict' when rebase fails
2. orchestrator.py _route_integration_failure() marks conflicts as 'blocked' state (non-retryable)
3. integration_queue.py has 'ready' and 'blocked' states but no backoff/retry tracking
4. No mechanism to distinguish infrastructure failures from real conflicts
5. No bounded backoff or needs-human transition

PLAN:
1. Add repair attempt tracking to integration queue (attempts counter exists but needs tuning)
2. Implement backoff logic: only retry after timeout or health check passes
3. Add explicit 'needs_human' state for exhausted repairs
4. Detect recoverable failures (401, provider errors) vs real conflicts
5. Route infrastructure failures to retryable state after bounded wait
6. Add tests for conflict + 401, provider failure, successful retry, repeated failure, restart scenarios
---
author: oompah
created: 2026-07-30 15:44
---
DISCOVERY: Found the current architecture:

1. integration_executor.py returns status='conflict' when rebase fails
2. orchestrator._route_integration_failure() marks as 'blocked' permanently  
3. Issue gets NEEDS_REBASE status, dispatches merge-conflict agent
4. If repair worker exits with infrastructure failure, no retry mechanism exists

Key code sections:
- integration_queue.py: tracks 'ready'/'blocked' states with simple fail() method
- integration.py: IntegrationRecord has 'attempts' counter but no backoff tracking
- provider_health.py: defines recoverable failures (auth_failed, rate_limited, overloaded, timeout)
- orchestrator.py:4944-5050: _route_integration_failure() and _execute_integration_item()

IMPLEMENTATION PLAN:
1. Add backoff_until timestamp to IntegrationRecord to track retry cooldown
2. Add infrastructure_failure_reason field to track failure classification
3. Add max_repair_attempts limit to configuration
4. Implement repair attempt counter and exhaustion detection
5. Add 'needs_human' state to INTEGRATION_STATES
6. Modify _route_integration_failure() to:
   - Detect infrastructure failures from error messages
   - Route to 'ready' with backoff_until for retryable failures
   - Route to 'needs_human' after max attempts exhausted
7. Update integration queue recovery logic to respect backoff_until
8. Add tests for: real conflict, 401, provider failure, successful retry, repeated failure/backoff, restart, no duplicate workers, needs_human exhaustion
---
<!-- COMMENTS:END -->
