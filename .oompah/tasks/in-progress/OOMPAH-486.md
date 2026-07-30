---
id: OOMPAH-486
type: feature
status: In Progress
priority: 1
title: Add terminal-audit metrics, maintenance health, and actionable alerts
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-483
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:25.195304Z'
updated_at: '2026-07-30T05:13:29.825998Z'
work_branch: epic-OOMPAH-460--task-OOMPAH-486
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4e7f3870005234da335ab42730b57e4a6e6cd1432e2297b0d9226918d8bae59f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:08:00.115630+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed active OOMPAH-475, OOMPAH-483, and sibling\
    \ tasks OOMPAH-484/485/487/488/489. They cover auditor dispatch, bypass detection,\
    \ APIs, UI, documentation, and lifecycle tests\u2014not metrics/maintenance health/alerting.\
    \ Historical OOMPAH-257 and OOMPAH-272 are terminal and were excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 1d974c55-6a77-4044-be66-f945b96ef83e
oompah.work_branch: epic-OOMPAH-460--task-OOMPAH-486
oompah.task_costs:
  total_input_tokens: 16623045
  total_output_tokens: 47361
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 16418536
      output_tokens: 28927
      cost_usd: 0.0
    sonnet:
      input_tokens: 119736
      output_tokens: 17845
      cost_usd: 0.0
    opus:
      input_tokens: 84773
      output_tokens: 589
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 2610630
    output_tokens: 8447
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:08:00.114490+00:00'
  - profile: default
    model: haiku
    input_tokens: 13806714
    output_tokens: 20151
    cost_usd: 0.0
    recorded_at: '2026-07-29T19:38:29.622527+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 74
    output_tokens: 16912
    cost_usd: 0.0
    recorded_at: '2026-07-29T19:54:54.651670+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 119662
    output_tokens: 933
    cost_usd: 0.0
    recorded_at: '2026-07-29T19:56:16.686338+00:00'
  - profile: deep
    model: opus
    input_tokens: 84773
    output_tokens: 589
    cost_usd: 0.0
    recorded_at: '2026-07-29T19:57:22.672903+00:00'
  - profile: default
    model: haiku
    input_tokens: 1192
    output_tokens: 329
    cost_usd: 0.0
    recorded_at: '2026-07-29T20:13:46.249012+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-460--task-OOMPAH-486
  base_branch: epic-OOMPAH-460
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T04:57:16.556178+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-486__20260729T195540Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: frontend
    source_branch: epic-OOMPAH-460--task-OOMPAH-486
    source_sha: 160b41761328dfad56d30cef0f572f9e4747338c
    completed_at: '2026-07-29T19:56:16.690744+00:00'
  - run_id: OOMPAH-486__20260729T195658Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: frontend
    source_branch: epic-OOMPAH-460--task-OOMPAH-486
    source_sha: 160b41761328dfad56d30cef0f572f9e4747338c
    completed_at: '2026-07-29T19:57:22.682164+00:00'
---
## Summary

Implementation scope

Track counters/gauges for queued, running, passed, failed, retried, stale-discarded, overridden, grandfathered, and no-independent-candidate audits, plus oldest queue age and last successful audit time. Surface them in the existing snapshot/maintenance status shapes. Add dashboard alerts only when no independent candidate exists, an audit exceeds the configured attempt/age threshold, queue recovery fails, or persistence is corrupt. Deduplicate by project/task/audit and clear alerts on recovery. Normal queued/running/passed audits must not alert.

Tests

Use deterministic clocks to cover metric increments, restart restoration, per-project isolation, oldest age, alert threshold/dedup/clear, no-candidate instructions, corrupt persistence, and absence of normal-operation alerts. Run observability tests and make test.

Acceptance criteria

Operators can distinguish healthy validation throughput from an actionable audit stall without receiving routine operating-procedure noise.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:08
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 29
- Tokens: 2.6M in / 8.4K out [2.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 42s
- Log: OOMPAH-486__20260729T020423Z.jsonl
---
author: oompah
created: 2026-07-29 18:27
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:27
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 19:38
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 235
- Tokens: 13.8M in / 20.2K out [13.8M total]
- Cost: $0.0000
- Exit: terminated, Duration: 1h 11m 0s
- Log: OOMPAH-486__20260729T182841Z.jsonl
---
author: oompah
created: 2026-07-29 19:39
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 19:39
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 19:45
---
Understanding: OOMPAH-486 adds terminal-audit observability metrics and actionable alerts. Backend work (TerminalAuditMetrics, TerminalAuditAlertRegistry, orchestrator integration) is complete across 3 commits. All 9 backend tests pass. The dashboard alerts-banner already renders state.alerts (which includes terminal-audit alerts when triggered). My frontend task is to add a visible audit throughput stat to the agent-bar that shows queued/running audit counts during healthy operation, hidden when idle. This gives operators a glance at healthy throughput without noise.
---
author: oompah
created: 2026-07-29 19:54
---
Agent failed: errored. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-07-29 19:54
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 112, Tool calls: 81
- Tokens: 74 in / 16.9K out [17.0K total]
- Cost: $0.0000
- Exit: error, Duration: 15m 52s
- Log: OOMPAH-486__20260729T193911Z.jsonl
---
author: oompah
created: 2026-07-29 19:55
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-29 19:55
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 19:56
---
Agent completed successfully in 45s (120595 tokens)
---
author: oompah
created: 2026-07-29 19:56
---
Run #3 [attempt=3, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 2
- Tokens: 119.7K in / 933 out [120.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 45s
- Log: OOMPAH-486__20260729T195540Z.jsonl
---
author: oompah
created: 2026-07-29 19:56
---
Agent completed without closing this issue (45s (120595 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 19:56
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-29 19:56
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 19:57
---
Agent completed successfully in 34s (85362 tokens)
---
author: oompah
created: 2026-07-29 19:57
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 1
- Tokens: 84.8K in / 589 out [85.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 34s
- Log: OOMPAH-486__20260729T195658Z.jsonl
---
author: oompah
created: 2026-07-29 19:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 19:57
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 20:03
---
**Understanding**: OOMPAH-486 implements terminal-audit observability. Backend (TerminalAuditMetrics, TerminalAuditAlertRegistry, orchestrator integration) is complete with 3 commits and passing tests. The frontend task is to add visible audit throughput stats to the dashboard UI showing queued/running audit counts during healthy operation, hidden when idle. The snapshot exposes metrics via orchestrator.get_snapshot()["terminal_audit"] and alerts via orchestrator.get_snapshot()["alerts"]. Will explore the frontend structure and implement the UI component to render this data.
---
author: oompah
created: 2026-07-29 20:06
---
**Discovery**: Found terminal-audit metrics are exposed via orchestrator.get_snapshot()["terminal_audit"] and broadcast to dashboard via WebSocket state updates. The agent-bar component in oompah/templates/dashboard.html currently shows Agents, Tokens, Cost, Budget, Reviews, Proposed foci, and Questions. Will add an audit throughput stat to display queued/running audit counts during active audit validation, hidden when idle. This satisfies the requirement to help operators distinguish healthy throughput from audit stalls without routine-operation noise.
---
author: oompah
created: 2026-07-29 20:12
---
**Implementation**: Added audit throughput stat to dashboard agent-bar (oompah/templates/dashboard.html):

1. HTML element: New agent-stat span showing 'Audits: Xq/Yr' format (q=queued, r=running) with aria-label for accessibility
2. JavaScript function: updateAuditThroughputStat() receives terminal_audit metrics from state and conditionally displays the stat only when queued>0 or running>0
3. State integration: Wired into handleStateUpdate() to receive state.terminal_audit from WebSocket broadcasts

The stat is hidden when idle (both queued and running are 0), preventing routine-operation noise while making active validation throughput immediately visible to operators. Backend metrics (queued, running counts) are provided via orchestrator.get_snapshot()["terminal_audit"], alleviating the need for operators to dig through logs or metrics endpoints.
---
author: oompah
created: 2026-07-29 20:13
---
**Verification**: All tests pass:

✓ test_terminal_audit_observability.py — 9/9 passed
  - Lifecycle metrics and oldest age deterministic
  - Queue age and project isolation survive restart
  - Threshold alerts deduplicate and clear on recovery
  - Normal queue/running/passed states have no alerts
  - No-candidate alert has actionable instructions
  - Corrupt persistence is visible
  - Orchestrator snapshot and alert recovery shapes
  - Queue recovery alert survives snapshots
  - Running audits don't emit queue-age alerts

✓ test_dashboard_review_badge.py — 1/1 passed

Frontend implementation complete: audit throughput stat displays queued/running counts in the agent-bar only during active validation, hidden when idle. Operators can now distinguish healthy throughput from actionable audit stalls without receiving routine-operation alerts.
---
author: oompah
created: 2026-07-29 20:13
---
Completed frontend audit throughput stat for dashboard agent-bar. Displays queued/running audit counts during active validation, hidden when idle. Backend metrics (TerminalAuditMetrics, TerminalAuditAlertRegistry, orchestrator integration) shipped across 3 commits with all 9 backend tests passing. Frontend now provides complete observability: operators can distinguish healthy throughput from actionable audit stalls without routine-operation noise.
---
author: oompah
created: 2026-07-29 20:13
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 73
- Tokens: 1.2K in / 329 out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 9s
- Log: OOMPAH-486__20260729T195744Z.jsonl
---
author: oompah
created: 2026-07-30 04:57
---
Integration found a rebase conflict on `epic-OOMPAH-460--task-OOMPAH-486`. Resolve it against `epic-OOMPAH-460`, run the required tests, push the same private branch, and `oompah task submit` it again.
---
author: oompah
created: 2026-07-30 04:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 04:57
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 05:13
---
Rebase conflict resolved: Epic branch added top-level 'audits' key at the same snapshot location where this branch adds 'terminal_audit'. Resolved by keeping both keys — 'audits' for legacy _audit_metrics compatibility, 'terminal_audit' for the stable API consumer shape. All 122 focused tests pass (9 observability, 104 coordinator, 9 status interfaces). Branch rebased onto epic-OOMPAH-460 at 12f63352b and force-pushed.
---
<!-- COMMENTS:END -->
