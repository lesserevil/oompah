---
id: OOMPAH-856
type: task
status: Open
priority: null
title: Make integrated-audit recovery alerts prescribe an accepted action
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T06:57:39.271491Z'
updated_at: '2026-08-06T16:31:35.746024Z'
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 665e46e6-1213-4e0a-94b9-f5c5c4e567ca
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T16:31:09.300361+00:00'
  claim_expires_at: '2026-08-06T17:01:09.300361+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a98a05bd-3fb3-455f-8fc9-453cf61f12e6
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-856
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-856
  base_branch: epic-OOMPAH-763
  base_sha: 6b67846406858b585ce47939f70bec76eb706fe8
  updated_at: '2026-08-06T16:31:28.231251+00:00'
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
<!-- COMMENTS:END -->
