---
id: OOMPAH-595
type: feature
status: Ready to Integrate
priority: 1
title: Expose separate operator and worker task-auth health signals
parent: OOMPAH-586
children: []
blocked_by:
- OOMPAH-593
- OOMPAH-594
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:56.897824Z'
updated_at: '2026-07-30T15:50:18.053588Z'
work_branch: epic-OOMPAH-586--task-OOMPAH-595
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5599144d8549cf413f0b3bfec2f0109e3cca03737c85cfab4397a53213de6eb8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T15:30:33.099442+00:00'
  matched_identifiers: []
  evidence: "I acknowledge the coordination message. The fact that OOMPAH-594 is marked\
    \ as both a \"dependency\" and \"epic-sibling\" of OOMPAH-595 (not a duplicate)\
    \ reinforces my conclusion:\n\n**Dependency Relationship Analysis:**\n- If OOMPAH-595\
    \ were a duplicate of OOMPAH-594, there would be no blocking dependency\u2014\
    the tasks would be consolidated into one.\n- The blocking dependency indicates\
    \ OOMPAH-595 is sequential work that builds on or requires OOMPAH-594's implementation\
    \ first.\n- Epic-sibling status confirms they are distinct tasks within the same\
    \ parent epic (OOMPAH-586).\n\nThis confirms the tasks are related but separate\
    \ pieces of work within the authentication health monitoring epic.\n\n---\n\n\
    **Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** No existing task in open, backlog, merged,\
    \ or archived states covers OOMPAH-595's scope (separate operator Basic-auth and\
    \ worker task-handoff health signals with 401/403 redaction and credential masking).\
    \ OOMPAH-594 is a blocking dependency, not a prior implementation\u2014the dependency\
    \ relationship confirms they are distinct, sequential tasks within epic OOMPAH-586,\
    \ not duplicates."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: bba6dc8b-569b-4934-85c6-4ee1dcf641e9
oompah.work_branch: epic-OOMPAH-586--task-OOMPAH-595
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-586--task-OOMPAH-595
  head_sha: a3505cc11ef2a696dca47912083a9e54b9d7bafd
  submitted_at: '2026-07-30T15:50:15.824542+00:00'
  updated_at: '2026-07-30T15:50:15.824542+00:00'
oompah.task_costs:
  total_input_tokens: 46973
  total_output_tokens: 1360
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46973
      output_tokens: 1360
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 859
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:30:33.098859+00:00'
  - profile: default
    model: haiku
    input_tokens: 46963
    output_tokens: 501
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:31:04.223935+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-595__20260730T152855Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-586--task-OOMPAH-595
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:30:33.105446+00:00'
  - run_id: OOMPAH-595__20260730T153048Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: frontend
    source_branch: epic-OOMPAH-586--task-OOMPAH-595
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:31:04.228512+00:00'
---
## Summary

Implementation scope

Add safe health probes and alerts that distinguish operator Basic-auth configuration drift from scoped task-handoff capability failures. Count/redact 401 and 403 outcomes by authentication path, report whether a worker token was minted and accepted without reporting the token, and provide actionable operator guidance. Avoid alerting on intentional unrelated-task denial. Relevant files include task_handoff instrumentation, task CLI/server middleware, service health/alerts APIs, dashboard, and docs troubleshooting.

Tests

Cover healthy operator and worker paths, stale operator credentials, missing/expired worker token, intentional scope denial, alert clear after recovery, restart persistence where appropriate, and redaction. Run focused auth/health/UI tests and make test.

Acceptance criteria

Operators can tell which authentication plane failed and how to recover it; secrets/capabilities never appear in logs, state JSON, alerts, or task comments.

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
created: 2026-07-30 15:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 23
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4m 20s
- Log: OOMPAH-595__20260730T152251Z.jsonl
---
author: oompah
created: 2026-07-30 15:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:30
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 50, Tool calls: 21
- Tokens: 10 in / 859 out [869 total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 47s
- Log: OOMPAH-595__20260730T152855Z.jsonl
---
author: oompah
created: 2026-07-30 15:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:30
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:31
---
Agent completed successfully in 22s (47464 tokens)
---
author: oompah
created: 2026-07-30 15:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 47.0K in / 501 out [47.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 22s
- Log: OOMPAH-595__20260730T153048Z.jsonl
---
author: oompah
created: 2026-07-30 15:31
---
Agent completed without closing this issue (22s (47464 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 15:31
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 15:31
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:36
---
Understanding: Implementing separate operator and worker task-auth health signals. Plan:
1. New oompah/auth_health.py module: thread-safe counters for operator Basic-auth 401s and worker task-handoff 401/403/minted/accepted events
2. Instrument server.py middleware to count operator 401s (without leaking credentials or auth details)
3. Instrument task-handoff endpoint to count worker failures (scope denials excluded from alerts per spec)
4. Expose auth_health dict in orchestrator get_snapshot()
5. Add auth health UI panel in dashboard.html showing separate operator/worker health with recovery guidance
6. Tests in test_auth_health.py and test_task_handoff.py

Key design: operator plane = HTTP Basic failures; worker plane = task-capability failures; intentional scope denials (wrong action) never alert.
---
author: oompah
created: 2026-07-30 15:50
---
Implementation complete. Delivered:

**oompah/auth_health.py** (new): Thread-safe OperatorAuthHealth and WorkerAuthHealth counters with 15-min sliding window. Separate tracking for: operator 401s; worker token minting, acceptance, 401s, 403-scope rejections, and 403-action intentional denials. auth_health_snapshot() and auth_health_alerts() for API consumption.

**oompah/server.py**: Wired record_operator_401() in BasicAuthMiddleware on 401 deny; wired record_worker_401/403_scope/403_action/token_accepted() at each outcome in api_task_handoff(). Intentional action denials counted separately, never alert.

**oompah/orchestrator.py**: _issue_task_handoff_token() calls record_worker_token_minted() on success; get_snapshot() includes auth_health dict and auth_health_alerts() merged into alerts list.

**oompah/templates/dashboard.html**: New .auth-health-banner with plane badge styles (ok/degraded/never-minted); renderAuthHealthBanner() shows two compact badges, expands on degradation with actionable recovery guidance; auth_health: alerts excluded from generic banner. Accessible: role=status, aria-live.

**docs/authentication.md**: New 'Auth Health Dashboard Signals' section documenting both planes and scope denial clarification.

**Tests**: 28 unit tests (test_auth_health.py) + 6 integration tests (test_server_auth.py). 159 total related tests pass.
---
author: oompah
created: 2026-07-30 15:50
---
Add separate operator and worker task-auth health signals with dashboard UI. New oompah/auth_health.py module tracks HTTP Basic 401s (operator plane) and task-handoff token minting/acceptance/401/403-scope/403-action (worker plane) in thread-safe sliding windows. Instrumented server middleware and task-handoff endpoint. Orchestrator get_snapshot() exposes auth_health dict and auth_health_alerts() in alerts. Dashboard shows two plane badges with actionable recovery guidance when degraded; intentional action denials never alert. 34 new tests; 159 related tests pass.
---
<!-- COMMENTS:END -->
