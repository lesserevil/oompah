---
id: OOMPAH-1011
type: bug
status: Open
priority: 1
title: Do not fence published workflow admission on an unaccepted scan allocation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T02:15:28.085531Z'
updated_at: '2026-08-11T02:15:42.447828Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: o1005-allocated-generation-admission
  request_fingerprint: e552e67c522a324a094c1ec5dc6006b6e8a6623e56450ab0445998e2b5220988
---
## Summary

Triggered by: OOMPAH-1005

Triggered by: OOMPAH-1005 and the live OOMPAH-940 rollout.

Problem: the retained-effect completion wake added by OOMPAH-1005 is delivered, but fast admission rejects the still-authoritative published snapshot as soon as a newer full scan merely allocates a generation. The admission fence currently requires allocated == accepted == published == cached cut. During a slow source collection, allocation alone diverts a valid completion wake into another full reconciliation. With same-task ownership serialization, only one older OOMPAH-940 imperative job drains per multi-minute scan and the current successor remains queued, creating avoidable liveness-overdue loops.

Scope: distinguish captured/allocated generation from accepted authority. Fast admission and claim predicates should require accepted == published == cached cut and must not be invalidated by an allocated-but-unaccepted scan. Once a newer scan accepts, preserve the existing stale-cut fence. Keep snapshot publication CAS, pause/quiesce/drain semantics, transactional task ownership, bounded coalescing, and genuine concurrent tracker-write supersession unchanged. Relevant code: workflow runtime admission, workflow job store generation predicates, and orchestrator reconcile completion wakes.

Required tests: add a production-shaped real-store/runtime regression that publishes a cut containing a retained job and same-task successor, blocks a newer reconciliation after generation allocation but before acceptance, completes the retained job as SUPERSEDED, and proves the successor is claimed immediately without a full-sync wait. Revise generation-fence unit tests so allocation alone remains admissible but acceptance of a newer generation fences the old cut. Cover pause/quiesce, real external tracker mutation, no-claimable-work coalescing, and state/lease convergence.

Acceptance: allocated-but-unaccepted scans cannot starve current queued durable work; accepted newer authority still fences stale work; focused tests and the complete Makefile gate pass; live canary drains a same-task successor without waiting for another full scan and shows zero divergence, overdue, action-required, and exhausted jobs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

