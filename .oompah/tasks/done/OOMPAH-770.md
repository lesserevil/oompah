---
id: OOMPAH-770
type: epic
status: Done
priority: 1
title: Enforce universal nonterminal liveness and truthful operator alerts
parent: OOMPAH-763
children:
- OOMPAH-784
- OOMPAH-795
- OOMPAH-796
- OOMPAH-821
blocked_by: []
start_blocked_by: &id001
- OOMPAH-765
- OOMPAH-766
labels:
- rebase-requested
assignee: null
created_at: '2026-08-04T13:56:03.317296Z'
updated_at: '2026-08-10T01:20:18.547698Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f78f6258ac71
    project_id: proj-14849f1b
    task_id: OOMPAH-770
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 02fbc812f8fddb7eaea74b739805db91d1b21710392021aa1c0465d65613f78f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope and its completed dependency wave are contained in that validated
      head; owner override avoids fabricating a separate branch/integration generation.
    created_at: '2026-08-08T16:30:56.199918+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-770
    target_state: Done
    evidence_fingerprint: 02fbc812f8fddb7eaea74b739805db91d1b21710392021aa1c0465d65613f78f
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:31:04.055799+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Historical audited Done record lacks safe exact current landing proof;
      retain immutable terminal provenance and retire recurring reassessment without
      creating new work.
    marked_at: '2026-08-10T01:20:16.998645+00:00'
    updated_at: '2026-08-10T01:20:16.998645+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Historical audited Done record lacks safe exact current landing proof;
        retain immutable terminal provenance and retire recurring reassessment without
        creating new work.
      recorded_at: '2026-08-10T01:20:16.998645+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Implement a universal liveness controller driven exclusively by WorkDecision. Every nonterminal task must be exactly one of runnable, durably owned, blocked by named prerequisites, scheduled for retry, or explicitly requiring operator action. Scan on relevant events plus a bounded full-sync safety interval; detect missing/conflicting/expired/impossible dispositions; enqueue safe recovery jobs rather than directly changing status; and escalate only when automatic recovery is unavailable or exhausted. Expose a Why is this task not progressing API/UI projection with owner, reason, evidence revision, next reassessment, and recovery action. Make normal queues, retries, backoff, active repair, audit launch rotation, and capacity waits informational/task-local; reserve global warnings for action_required conditions. Add SLO metrics for Open/Ready/In Validation/In Review and restart convergence. Required tests: totality, bounded-age violations, idempotent recovery, alert transitions, no duplicate escalation, UI/action parity, and all current watchdog cases. Acceptance: no nonterminal unknown state survives a full-sync interval; all synthetic stalls recover or escalate with concrete instructions; global alerts are actionable and clear automatically from current facts.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Hard-start prerequisites OOMPAH-765 and OOMPAH-766 have landed. Promoting this epic and its first unblocked child so the server can advance the liveness work in parallel with OOMPAH-768.
---
author: oompah
created: 2026-08-06 00:13
---
Critical-path topology repair completed while project dispatch was paused. epic-OOMPAH-770 had no unique commits and was safely fast-forwarded from f1e7925b7263f980517f943291102c8c83335ed2 to exact parent epic-OOMPAH-763 head 58ffd477b19f370c7ed53a191e1a05580b016c85. The remote ref is verified and clean; this makes OOMPAH-806 and OOMPAH-807 code reachable for OOMPAH-796 and OOMPAH-821.
---
author: oompah
created: 2026-08-08 16:31
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope and its completed dependency wave are contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
