---
id: OOMPAH-1011
type: bug
status: In Progress
priority: 1
title: Do not fence published workflow admission on an unaccepted scan allocation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T02:15:28.085531Z'
updated_at: '2026-08-11T03:05:38.620408Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 02:16
---
Claimed for direct-owner implementation in the current systemic workflow recovery program. Work will be isolated on this task branch, covered by focused regression tests, independently reviewed, fully gated, pushed, and submitted through the protected delivery path.
---
author: oompah
created: 2026-08-11 02:26
---
Implementation is committed and pushed at exact head a28cac7f6b315fb4cf2a05f14e78cf3b16261288. Fast admission now treats accepted+published authority as executable during a merely allocated scan, explicitly binds managed candidates to the published membership generation, and still fences immediately when a replacement generation is accepted. The production-shaped real-store/runtime regression proves a superseded same-task retained event wakes and completes its managed successor while a newer source scan is blocked after allocation; a concurrent tracker publication mutation still supersedes that scan. Validation: 418 focused workflow/job/runtime/worker/orchestrator tests passed, the exact five-test race/fence set passed 100/100 across 20 xdist runs, terminal mutation scan 21/21, and secret/diff/compile checks passed. Branch is clean and up to date with origin.
---
author: oompah
created: 2026-08-11 02:36
---
Independent-review correction is committed and pushed at exact head 092debf174fe4dd7521669690a79603ecf216eef. Removed the invalid global-published-generation equality from individual membership rows: bounded scans may carry an expected-but-unevaluated task's prior membership/cursor forward. Accepted==published authority, cursor/member equality, candidate/cursor job-generation equality, and required-cut CAS remain intact. New exact store regression publishes A/B in generation 1, publishes generation 2 after evaluating only A, proves B retains generation-1 membership/cursor and remains claimable under required generation 2. Validation: 419 adjacent tests passed; six exact allocation/acceptance/bounded-membership/race tests passed 120/120 over 20 xdist runs; mutation scan 21/21 and secret/diff/compile checks passed. Branch is clean and up to date with origin.
---
author: oompah
created: 2026-08-11 03:05
---
Independent re-review accepted exact head 092debf174fe4dd7521669690a79603ecf216eef with no findings. Accepted/published authority remains the fast-admission fence, bounded carry-forward membership remains claimable, and a genuinely accepted newer generation still fences stale work. The combined four-fix branch passed 827 changed-path tests.
---
<!-- COMMENTS:END -->
