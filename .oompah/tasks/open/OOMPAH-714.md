---
id: OOMPAH-714
type: task
status: Open
priority: null
title: Do not cancel an unrelated branch gate when an auditor attempt retires
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T01:03:08.223719Z'
updated_at: '2026-08-03T01:03:36.998098Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0c34ea48f316eddc2939578204da8fde3861fc49cb452febf4b382258d6d5bc8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 60b653f0-cdef-432f-bc34-0d238c25452f
  claim_owner: ac52e8ec-836b-4534-92a2-d2acfef0120b
  claimed_at: '2026-08-03T01:03:31.089590+00:00'
  claim_expires_at: '2026-08-03T01:33:31.089590+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 2e5e8d97-302f-423b-a69c-465cb5dcb30c
---
## Summary

Triggered by concurrent OOMPAH-709 completion audit and OOMPAH-710 branch gate on 2026-08-03. OOMPAH-710 was actively running its exact-head isolated make test gate at 205f413440767c5c2c94c641504f96f6a71c77bb. At 00:57:41 the OOMPAH-709 auditor exhausted its policy-denial limit; at 00:57:42 Oompah logged Interrupted 1 active quality gate process group, then Discarding superseded quality gate for OOMPAH-710. The OOMPAH-710 branch and accepted head had not changed. Oompah moved on to OOMPAH-711 and surfaced standalone_ready_delivery:OOMPAH-710 saying its configured gate did not pass, stranding 710 despite no test failure.

Implementation scope:
- Trace cancellation ownership across terminal-audit retirement, running-entry termination, standalone delivery authority, and BranchQualityGate generations.
- Ensure stopping or rotating an auditor can terminate only that auditor provider process and detached audit worktree; it must never cancel a branch gate for another task.
- Key every quality-gate cancellation to the exact project/task/head/authority generation and reject cross-task or generationless cancellation outside full orchestrator shutdown.
- Treat an intentionally superseded gate as retryable for the same unchanged accepted head; do not cache it as a failed gate or strand the task with a no-active-delivery warning.
- Make active gate ownership visible in health/state so the UI can distinguish running, interrupted-for-retry, failed, and idle.

Relevant evidence: oompah.log around 2026-08-03T00:57:41Z through 00:57:45Z; oompah/quality_gate.py active process registry and cancel_generation; oompah/orchestrator.py terminal auditor retirement, standalone delivery authority revocation, and review gate handling.

Required tests:
- Run task A completion auditor concurrently with task B branch gate, exhaust or rotate A, and prove B process group survives and its result is accepted.
- Supersede B explicitly and prove only B exact generation stops.
- Interrupt B for a retryable infrastructure reason and prove unchanged accepted head is retried rather than alerted as a test failure.
- Full orchestrator shutdown still terminates every gate process group.
- State and alert tests report the correct active owner and clear after recovery.

Acceptance criteria:
- Replaying the OOMPAH-709/OOMPAH-710 sequence cannot interrupt the unrelated gate.
- A cross-task cancellation request has no effect and emits diagnostic ownership evidence.
- OOMPAH-710-style interrupted work automatically re-enters delivery without operator resubmission.
- Focused quality-gate, terminal-audit, standalone-delivery, and orchestrator tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 01:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 01:03
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
