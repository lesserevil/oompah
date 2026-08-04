---
id: OOMPAH-771
type: epic
status: Backlog
priority: 1
title: Retire legacy reconcilers and modularize the orchestrator
parent: OOMPAH-763
children:
- OOMPAH-787
- OOMPAH-794
- OOMPAH-798
blocked_by: []
start_blocked_by: &id001
- OOMPAH-768
- OOMPAH-770
- OOMPAH-767
- OOMPAH-769
- OOMPAH-806
labels: []
assignee: null
created_at: '2026-08-04T13:56:05.119669Z'
updated_at: '2026-08-04T21:31:12.002162Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Complete the migration by deleting superseded workflow code and documenting the supported architecture. Remove duplicate eligibility summaries, direct status writers, read-time repair side effects, status-specific watchdog recovery now covered by liveness, obsolete process-local authority maps, and fire-and-forget lifecycle futures. Reduce _tick to event intake, fact refresh, decision evaluation, and durable job scheduling. Split the 37k-line orchestrator into cohesive workflow modules without changing public behavior; keep project/tracker/Git adapters separate from pure rules. Remove shadow flags only after production canary evidence, update user/operator docs, publish recovery and rollout guidance, and enforce architectural import/write boundaries. Required tests: full make test, architectural dependency tests, API compatibility, clean restart/upgrade from pre-migration state, rollback before final flag removal, and production-like soak. Acceptance: legacy paths are deleted rather than retained; production workflow LOC and branch complexity materially decline; one transition writer/decision engine/job ledger/liveness controller remain; repository and docs contain no contradictory workflow implementation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

