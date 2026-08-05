---
id: OOMPAH-821
type: task
status: Backlog
priority: null
title: Align terminal-audit recovery alerts with retryable mixed-attempt histories
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T05:11:56.700024Z'
updated_at: '2026-08-05T05:11:56.700024Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression: OOMPAH-745 is integrated at exact head b08a12057afed4e7af5080e7e47522eed16dc2ce and its terminal-audit chain completed in no_auditor after earlier abandoned/finalization-failure attempts. The integration sweep emits terminal_audit_recovery guidance telling an owner to rearm, but both supported owner commands are rejected with HTTP 409 'No matching exhausted audit': evidence-addendum rearm is correctly limited to missing_evidence, while infrastructure rearm currently requires every historical attempt classification to be NO_AUDITOR/INFRASTRUCTURE_ERROR/POLICY_INCOMPATIBILITY. The task remains Ready to Integrate with an integrated queue row and a permanent actionable warning despite exact-head focused verification.\n\nImplementation scope: make the sweep/recovery classifier and TerminalTransitionCoordinator.retry_failed_audit share one canonical retry-eligibility decision; classify retryability from the terminal exhaustion outcome while preserving prior attempt history, or suppress/replace the alert with truthful supported action when a mixed chain is not retryable. Ensure same-head integration reflow cannot move an exhausted task into a state where the advertised recovery command is rejected. Preserve owner authentication, exact evidence fingerprint fencing, independent-auditor requirements, successful-audit finality, and evidence-addendum restriction to missing_evidence. Relevant files: oompah/terminal_transition_coordinator.py, oompah/orchestrator.py recovery alert/completion sweep, oompah/server.py error mapping, task CLI/operator docs if guidance changes.\n\nRequired tests: reproduce OOMPAH-745 with abandoned + finalization_failure + terminal no_auditor attempts, same-head integrated reflow, emitted alert, owner infrastructure retry, fresh pending audit, and alert clearing; prove alert/action parity for every supported terminal failure classification; prove missing-evidence still requires a current-fingerprint successful-check addendum; prove non-owner, changed fingerprint, successful completed audit, and repeated retry remain rejected/coalesced as appropriate; cover restart/sweep races without warning spam. Acceptance: every emitted terminal_audit_recovery action succeeds against the same durable snapshot or the UI gives a truthful non-retry action; OOMPAH-745 can re-enter independent audit without terminal override; focused coordinator/server/integration/observability tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

