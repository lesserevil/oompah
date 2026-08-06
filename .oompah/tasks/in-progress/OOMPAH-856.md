---
id: OOMPAH-856
type: task
status: In Progress
priority: null
title: Make integrated-audit recovery alerts prescribe an accepted action
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T06:57:39.271491Z'
updated_at: '2026-08-06T16:53:47.576230Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-856
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 090789d484e9f0f07a5f02055d487d36863cf2509dad9ab6a62d1d1acb192544
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T16:51:11.805538+00:00'
  matched_identifiers: []
  evidence: 'Project-owner review of the active systemic workflow corpus found no
    equivalent task: OOMPAH-856 uniquely aligns no_auditor recovery actions with coordinator
    eligibility and clears resolved integrated-audit alerts; the omitted structural
    peers cover distinct validation, quiesce, isolation, and delivery concerns.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T16:51:11.805538+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: 'Project-owner review of the active systemic workflow corpus
    found no equivalent task: OOMPAH-856 uniquely aligns no_auditor recovery actions
    with coordinator eligibility and clears resolved integrated-audit alerts; the
    omitted structural peers cover distinct validation, quiesce, isolation, and delivery
    concerns.'
oompah.agent_run_id: 6ccfc901-da26-4a4b-a17c-3f08a21a1f87
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-856
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-856
  base_branch: epic-OOMPAH-763
  base_sha: 6b67846406858b585ce47939f70bec76eb706fe8
  updated_at: '2026-08-06T16:31:28.231251+00:00'
oompah.task_costs:
  total_input_tokens: 48330
  total_output_tokens: 378
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 48330
      output_tokens: 378
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 48330
    output_tokens: 378
    cost_usd: 0.0
    recorded_at: '2026-08-06T16:31:59.738390+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-856__20260806T163141Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-856
    source_sha: 6b67846406858b585ce47939f70bec76eb706fe8
    completed_at: '2026-08-06T16:31:59.765992+00:00'
---
## Summary

Live regression on OOMPAH-745 on 2026-08-06. The integration recovery alert reported that exact integrated head b08a12057 had no active terminal audit because the prior record was already completed, and instructed an authenticated owner to rearm Done with audit_retry_evidence_addendum. The canonical fingerprint a7c99834908b matched exactly and successful integration, focused, and mutation-scan checks were supplied, but the coordinator rejected both ordinary audit retry and the exact evidence-addendum retry with No matching exhausted audit because the completed record failure classification was no_auditor rather than missing_evidence. An owner override moved the verified task to Done, yet the recovery alert remained visible after the terminal state changed. Implementation scope: align integrated-audit recovery classification, retry eligibility, and operator message; offer only an action the coordinator accepts for the exact record state; clear the recovery alert immediately and durably when a terminal override or terminal status resolves the task; preserve history, fingerprint CAS, owner authorization, and fail-closed behavior. Relevant code includes Orchestrator stage-integrated audit and recovery-alert arm and clear paths, TerminalTransitionCoordinator retry_failed_audit and override cleanup, task status interfaces, and state snapshot alerts. Required tests: replay integrated plus completed no_auditor with unchanged fingerprint; prove either owner rearm succeeds or the alert prescribes owner override, never impossible evidence rearm; matching missing_evidence still accepts validated addendum; wrong fingerprint and non-owner fail; successful override clears the alert in the same response generation and across restart; no warning reappears for Done. Acceptance criteria: every recovery alert action is executable for its record classification, resolved terminal tasks emit no stale integrated-audit warning, and focused delivery-plane, coordinator, status-interface, observability, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 16:30
---
Promoted to Open for managed server implementation in parallel. It has no start dependency and can repair accepted recovery actions and stale-alert clearing while the operator-owned audit/runtime branches validate.
---
author: oompah
created: 2026-08-06 16:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 16:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 16:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 48.3K in / 378 out [48.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 39s
- Log: OOMPAH-856__20260806T163141Z.jsonl
---
author: oompah
created: 2026-08-06 16:32
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-06 16:53
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
