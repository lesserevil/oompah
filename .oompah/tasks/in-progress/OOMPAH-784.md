---
id: OOMPAH-784
type: task
status: In Progress
priority: 1
title: Add workflow liveness SLO metrics and evidence-backed recovery health
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-796
labels: []
assignee: null
created_at: '2026-08-04T13:59:04.299718Z'
updated_at: '2026-08-06T07:10:02.719054Z'
work_branch: epic-OOMPAH-770--task-OOMPAH-784
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5404dc70da5f7e3380399fb9e43136f5867ac0014f98c08fe05d8ac977291778
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T03:54:04.039830+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: OOMPAH-784 is an original, non-duplicate task. It is a child task under
    epic parent OOMPAH-770 ("Enforce universal nonterminal liveness and truthful operator
    alerts"), dedicated to implementing the SLO metrics component mentioned in the
    epic scope. The closest active peer tasks (OOMPAH-795, OOMPAH-821) have distinct
    scopes: UI/projection alerting and terminal-audit recovery respectively. No active
    or archived task covers the specific work of instrumenting decision-age metrics,
    bounded cardinality tracking, health threshold configuration, and project/global
    summary exposure.

    I will now investigate whether OOMPAH-784 is a duplicate of any existing active
    task in the project corpus.


    ## Understanding OOMPAH-784


    **Title:** Add workflow liveness SLO metrics and evidence-backed recovery health


    **Scope:** Instrument time-to-owner/explanation tracking for task states (Open,
    Ready, In Validation, In Review, recovery, post-restart), track decision age,
    reassessment lateness, lease/retry deadlines, recoveries, escalations, and unexplained
    divergences with bounded cardinality. Add health thresholds via OOMPAH_* .env
    configuration and expose project/global summaries.


    **Key Requirements:**

    - Track metrics for workflow liveness (decision age, reassessment lateness, lease/retry
    deadlines, etc.)

    - Implement bounded cardinality

    - Add health thresholds via .env configuration

    - Expose project/global summaries

    - Comprehensive test coverage for SLO boundaries and health integration


    ## Examining Active Peer Tasks


    Filtering the corpus to **active, non-terminal tasks only** (excluding Done, Merged,
    Archived):


    ### OOMPAH-770: Enforce universal nonterminal liveness and truthful operator alerts
    (In Progress)

    - **Relationship:** PARENT EPIC of OOMPAH-784

    - **Scope:** Build a universal liveness controller with WorkDecision enforcement,
    recovery actions, API/UI projections

    - **Mentions SLO work:** "Add SLO metrics for Open/Ready/In Validation/In Review
    and restart convergence"

    - **Not a duplicate:** OOMPAH-770 is the parent epic; OOMPAH-784 is a dedicated
    child task to implement the SLO metrics component


    ### OOMPAH-795: Expose one why-not-progressing projection and make alerts truthful
    (Open)

    - **Scope:** API, dashboard, alerts consumption of WorkDecision; operator-actionable
    warnings only

    - **Focus:** UI/projection layer, not metrics instrumentation

    - **Not a duplicate:** Distinct scope (alerting/projection vs SLO metrics)


    ### OOMPAH-821: Align terminal-audit recovery alerts with retryable mixed-attempt
    histories (Ready to Integrate)

    - **Scope:** Terminal-a'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1d92bda4-0958-4a9e-8bfe-053931762b35
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-784
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-784
  base_branch: epic-OOMPAH-770
  base_sha: 2bc189d706a6afcf7ecc8b2f5ac8a572a93d522b
  updated_at: '2026-08-06T04:12:03.344679+00:00'
oompah.task_costs:
  total_input_tokens: 716
  total_output_tokens: 3717
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 672
      output_tokens: 2231
      cost_usd: 0.0
    sonnet:
      input_tokens: 44
      output_tokens: 1486
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2064
    cost_usd: 0.0
    recorded_at: '2026-08-06T03:54:04.038423+00:00'
  - profile: default
    model: haiku
    input_tokens: 662
    output_tokens: 167
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:11:31.116894+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 44
    output_tokens: 1486
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:46:55.314786+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-784__20260806T034651Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-770--task-OOMPAH-784
    source_sha: 2bc189d706a6afcf7ecc8b2f5ac8a572a93d522b
    completed_at: '2026-08-06T03:54:04.054991+00:00'
---
## Summary

Instrument time-to-owner/explanation for Open, Ready, In Validation, In Review, recovery, and post-restart reconstruction. Track decision age, reassessment lateness, lease/retry deadlines, recoveries, escalations, and unexplained divergences with bounded cardinality. Add health thresholds via OOMPAH_* .env configuration and expose project/global summaries. Required tests: fake-clock boundaries, resets on progress, no false overdue during active jobs, restart timestamp handling, cardinality bounds, and health/alert integration. Acceptance: configured SLO violations are measurable and attributable; healthy means every nonterminal task satisfies the liveness invariant, not merely that the server loop responds.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:19
---
Promoted from Backlog to Open after hard-start prerequisite OOMPAH-796 reached Done. Project is temporarily paused for the graceful cutover; dispatch normally on resume.
---
author: oompah
created: 2026-08-06 03:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 03:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 03:54
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 53s
- Log: OOMPAH-784__20260806T034651Z.jsonl
---
author: oompah
created: 2026-08-06 03:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 03:55
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 03:57
---
## Understanding

This task requires adding workflow liveness SLO (Service Level Objective) metrics to track time-to-owner/explanation for tasks in Open, Ready, In Validation, In Review states, plus recovery and post-restart handling.

### Key requirements:
1. **Instrument time-to-owner**: Track decision age, reassessment lateness, lease/retry deadlines, recoveries, escalations, unexplained divergences with bounded cardinality
2. **Configuration**: Add OOMPAH_* env variables for health thresholds
3. **Health exposure**: Project/global summaries via API health endpoints
4. **Testing**: fake-clock boundaries, progress resets, no false overdue during active jobs, restart timestamps, cardinality bounds, health/alert integration
5. **Acceptance criteria**: SLO violations are measurable and attributable; healthy means every nonterminal task satisfies liveness invariant

### Planned approach:
1. Create new `workflow_liveness_metrics.py` module for SLO instrumentation
2. Extend models to track time-to-owner and decision age per task status
3. Add OOMPAH_SLO_* configuration for thresholds (via .env.example)
4. Integrate with existing health endpoints (provider_health.py pattern)
5. Write comprehensive test suite with fake clock and state transitions
6. Expose metrics via API health endpoints alongside existing terminal_audit_health

### My focus:
As Oompah Tests Auth Specialist, I'll ensure:
- Clean API boundaries and proper health endpoint integration
- Robust test coverage with edge cases (fake clock, restarts, transitions)
- Proper instrumentation that doesn't expose internal state
---
author: oompah
created: 2026-08-06 04:11
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 39
- Tokens: 662 in / 167 out [829 total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 40s
- Log: OOMPAH-784__20260806T035513Z.jsonl
---
author: oompah
created: 2026-08-06 04:11
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 04:12
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 04:46
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 27
- Tokens: 44 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 34m 59s
- Log: OOMPAH-784__20260806T041211Z.jsonl
---
author: oompah
created: 2026-08-06 04:47
---
Direct-owner takeover after independent static review rejected checkpoint 8940760dc. The checkpoint adds only an unwired metrics module/tests: it is not consumed by ServiceConfig, UniversalTotalityLivenessController, orchestrator health/API/UI, or .env.example; it conflicts with workflow_reasons.LIVENESS_SLOS; status normalization and progress timestamps are wrong; incomplete scans can report healthy; cardinality caps are not enforced; and tests include a bare pass plus contradictory exact-boundary assertions. Preserved the clean checkpoint. Repair must derive bounded liveness projections from authoritative WorkDecision/controller facts, persist restart-safe ages/deadlines, wire project/global health with action_required-only warning semantics, and replace misleading tests before validation.
---
author: oompah
created: 2026-08-06 07:10
---
Independent static review REJECTED the current uncommitted repair. Blocking false-green paths remain: reassessment deadlines renew without progress; OWNED is treated as live without a durable job/lease; scheduler-truncated recovery can report healthy before materialization; cumulative/retained recovery and omission truth is lost; required restart/reload/multi-project behavioral coverage and configurable per-status SLOs are absent. Repair is in progress before any tests or gate submission.
---
<!-- COMMENTS:END -->
