---
id: OOMPAH-595
type: feature
status: In Validation
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
updated_at: '2026-07-31T00:44:57.839464Z'
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
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-586--task-OOMPAH-595
  base_branch: epic-OOMPAH-586
  base_sha: e0cff8ffd3319cf6d22dab914befea3222a1498d
  head_sha: ca49d0c25b30d149cb59f0af0bac57276c1f8120
  integrated_sha: ca49d0c25b30d149cb59f0af0bac57276c1f8120
  submitted_at: '2026-07-30T15:50:15.824542+00:00'
  updated_at: '2026-07-31T00:13:49.368284+00:00'
  dependency_heads:
    OOMPAH-594: 31a10b064158948503a7eaa646a1bfa7d1b35e55
    OOMPAH-593: 0a260f0279690a12fb056da0c8becb6f492f8c26
oompah.task_costs:
  total_input_tokens: 47188
  total_output_tokens: 54239
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46973
      output_tokens: 1360
      cost_usd: 0.0
    sonnet:
      input_tokens: 102
      output_tokens: 32089
      cost_usd: 0.0
    unknown:
      input_tokens: 113
      output_tokens: 20790
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
  - profile: standard
    model: sonnet
    input_tokens: 102
    output_tokens: 32089
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:50:39.236216+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 44
    output_tokens: 8148
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:18:52.888980+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 69
    output_tokens: 12642
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:44:51.255521+00:00'
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
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-e7bb1375c3e2: '2026-07-31T00:18:20.982747+00:00'
    attempt-05f1dc64fc23: '2026-07-31T00:44:24.685225+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-28e63397591c
    project_id: proj-14849f1b
    task_id: OOMPAH-595
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 38ac014f417de8e864404d3d18ff24f573f275257d88db9eab2164e0a203f255
    attempts:
    - version: 1
      attempt_id: attempt-e7bb1375c3e2
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 38ac014f417de8e864404d3d18ff24f573f275257d88db9eab2164e0a203f255
      created_at: '2026-07-31T00:14:01.504765+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T00:14:01.504765+00:00'
      branch_key: epic-OOMPAH-586--task-OOMPAH-595
      verdict: pass
      completed_at: '2026-07-31T00:18:20.982531+00:00'
      ended_at: '2026-07-31T00:18:20.982531+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-31T00:13:50.602334+00:00'
    updated_at: '2026-07-31T00:18:20.982531+00:00'
  - version: 1
    audit_id: audit-612591e71deb
    project_id: proj-14849f1b
    task_id: OOMPAH-595
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4818bf1084729de2ef0887490ea51286bb480ecbd823735d7271c4e0a3e7a8d5
    attempts:
    - version: 1
      attempt_id: attempt-05f1dc64fc23
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 4818bf1084729de2ef0887490ea51286bb480ecbd823735d7271c4e0a3e7a8d5
      created_at: '2026-07-31T00:39:00.790988+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T00:39:00.790988+00:00'
      branch_key: epic-OOMPAH-586--task-OOMPAH-595
      verdict: pass
      completed_at: '2026-07-31T00:44:24.685068+00:00'
      ended_at: '2026-07-31T00:44:24.685068+00:00'
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: Needs Human
    created_at: '2026-07-31T00:38:54.738900+00:00'
    updated_at: '2026-07-31T00:44:24.685068+00:00'
  - version: 1
    audit_id: audit-77e603230884
    project_id: proj-14849f1b
    task_id: OOMPAH-595
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 38ac014f417de8e864404d3d18ff24f573f275257d88db9eab2164e0a203f255
    attempts: []
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Needs Human
    created_at: '2026-07-31T00:44:54.940604+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e7bb1375c3e2
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 38ac014f417de8e864404d3d18ff24f573f275257d88db9eab2164e0a203f255
    created_at: '2026-07-31T00:14:01.504765+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T00:14:01.504765+00:00'
    branch_key: epic-OOMPAH-586--task-OOMPAH-595
  - version: 1
    attempt_id: attempt-05f1dc64fc23
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4818bf1084729de2ef0887490ea51286bb480ecbd823735d7271c4e0a3e7a8d5
    created_at: '2026-07-31T00:39:00.790988+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T00:39:00.790988+00:00'
    branch_key: epic-OOMPAH-586--task-OOMPAH-595
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
author: oompah
created: 2026-07-30 15:50
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 117
- Tokens: 102 in / 32.1K out [32.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 19m 13s
- Log: OOMPAH-595__20260730T153130Z.jsonl
---
author: oompah
created: 2026-07-31 00:13
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 00:14
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 00:14
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 00:18
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: ca49d0c25b30d149cb59f0af0bac57276c1f8120
- branch_name: epic-OOMPAH-586--task-OOMPAH-595
- working_tree: clean
- auth_health_module: oompah/auth_health.py (+363 lines)
- server_wiring: record_operator_401 at BasicAuthMiddleware; record_worker_401/403_scope/403_action/token_accepted at api_task_handoff
- orchestrator_wiring: record_worker_token_minted at _issue_task_handoff_token; auth_health + auth_health_alerts in get_snapshot
- dashboard_wiring: renderAuthHealthBanner + auth-health-banner with plane badges; auth_health: alerts filtered from generic banner
- docs_change: docs/authentication.md: new Auth Health Dashboard Signals section
- tests_auth_health: 28/28 pass
- tests_server_auth: 73/73 pass (6 counter-integration tests included)
- tests_task_handoff: 28/28 pass
- tests_orchestrator_handlers: 269/269 pass
- redaction_verified: snapshot uses booleans + counts only; no token/credential/Authorization in state JSON or alerts
- action_denial_semantics: 403 action counted separately (scope_denial_count); never surfaces as auth_health alert
---
author: oompah
created: 2026-07-31 00:18
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 38
- Tokens: 44 in / 8.1K out [8.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 50s
- Log: OOMPAH-595__20260731T001413Z.jsonl
---
author: oompah
created: 2026-07-31 00:37
---
The parent epic OOMPAH-586 merged from epic-OOMPAH-586, but this task was Done with work branch epic-OOMPAH-586--task-OOMPAH-595. Its work is not proven to be in the merged epic. Git evidence: OOMPAH-595 branch epic-OOMPAH-586--task-OOMPAH-595 has 1 unlanded commit(s), including ca49d0c25b30. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-31 00:37
---
The parent epic OOMPAH-586 merged from epic-OOMPAH-586, but this task was Needs Human with work branch epic-OOMPAH-586--task-OOMPAH-595. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-31 00:38
---
Repaired landing provenance after the approved OOMPAH-586 rebase: canonical task branch epic-OOMPAH-586--task-OOMPAH-595 now points from pre-rebase ca49d0c25 to rewritten commit 04d072a5f, which is a direct ancestor of merged outer target epic-OOMPAH-584 at cd08185c9. No implementation was missing; the rebase conflict resolution preserved both auth-health and terminal-audit health features. Requesting fresh Done validation on the rewritten evidence.
---
author: oompah
created: 2026-07-31 00:39
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 00:39
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 00:44
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head_local: ca49d0c25b30d149cb59f0af0bac57276c1f8120
- branch_head_origin: 04d072a5f1ade3a92506316ef102c84545b5fcd2
- outer_merge_head: cd08185c9 (PR #597 epic-OOMPAH-586 -> epic-OOMPAH-584)
- landing_relationship: 04d072a5f is direct parent of cd08185c9
- working_tree: clean
- auth_health_module: oompah/auth_health.py present; only counts+booleans in public surface
- operator_wiring: server.py:119,614 record_operator_401 in _BasicAuthMiddleware on 401 deny
- worker_wiring: server.py:3300,3336,3359,3361,3367 record_worker_401 / _403_scope / _403_action / _token_accepted at task-handoff endpoint outcomes
- mint_wiring: orchestrator.py:158,20001 record_worker_token_minted at handoff-token issue
- snapshot_wiring: orchestrator.py:25207-25208 auth_health dict plus auth_health_alerts merged into alerts
- dashboard_wiring: templates/dashboard.html:1210-1276 CSS; :2144-2150 banner; :2542 renderAuthHealthBanner; :2648 filter of auth_health: prefix; :2683 render call
- docs_change: docs/authentication.md Auth Health Dashboard Signals (line 769)
- tests_auth_health_suite: 28/28 pass
- tests_task_handoff_suite: 28/28 pass
- tests_server_auth_suite: 73/73 pass (1 unrelated deprecation warning)
- tests_orchestrator_handlers_suite: 269/269 pass
- tests_docs_authentication_contract_suite: 5/5 pass
- tests_dashboard_alert_suites: 64/64 pass
- redaction_verified: auth_health.py contains no sensitive-string references; snapshot returns only ints, bools, and static guidance strings
- action_denial_semantics: record_worker_403_action counted in scope_denial_count field only; never appears in build_alert output
---
author: oompah
created: 2026-07-31 00:44
---
The parent epic OOMPAH-586 merged from epic-OOMPAH-586, but this task was Done with work branch epic-OOMPAH-586--task-OOMPAH-595. Its work is not proven to be in the merged epic. Git evidence: OOMPAH-595 branch epic-OOMPAH-586--task-OOMPAH-595 has 1 unlanded commit(s), including ca49d0c25b30. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-31 00:44
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 63
- Tokens: 69 in / 12.6K out [12.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 49s
- Log: OOMPAH-595__20260731T003906Z.jsonl
---
<!-- COMMENTS:END -->
