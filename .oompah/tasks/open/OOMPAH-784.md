---
id: OOMPAH-784
type: task
status: Open
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
updated_at: '2026-08-06T03:54:18.744146Z'
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
oompah.agent_run_id: 3ec9cb63-b4a2-4e0f-85e6-baf527364b4e
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-784
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-784
  base_branch: epic-OOMPAH-770
  base_sha: 2bc189d706a6afcf7ecc8b2f5ac8a572a93d522b
  updated_at: '2026-08-06T03:46:21.612408+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2064
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2064
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2064
    cost_usd: 0.0
    recorded_at: '2026-08-06T03:54:04.038423+00:00'
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
<!-- COMMENTS:END -->
