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
updated_at: '2026-08-06T16:30:47.754056Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->
