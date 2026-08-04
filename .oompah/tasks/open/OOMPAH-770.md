---
id: OOMPAH-770
type: epic
status: Open
priority: 1
title: Enforce universal nonterminal liveness and truthful operator alerts
parent: OOMPAH-763
children:
- OOMPAH-784
- OOMPAH-795
- OOMPAH-796
blocked_by: []
start_blocked_by: &id001
- OOMPAH-765
- OOMPAH-766
labels: []
assignee: null
created_at: '2026-08-04T13:56:03.317296Z'
updated_at: '2026-08-04T21:42:49.508700Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
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
<!-- COMMENTS:END -->
