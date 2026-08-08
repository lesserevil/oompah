---
id: OOMPAH-798
type: task
status: In Progress
priority: 1
title: Split the monolithic orchestrator into cohesive workflow modules
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-794
labels: []
assignee: null
created_at: '2026-08-04T13:59:30.266221Z'
updated_at: '2026-08-08T09:45:21.661304Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Refactor the remaining orchestrator after legacy deletion into explicit adapters/coordinators: event intake/fact refresh, decision scheduling, durable jobs, transitions, integration, audit, review, implementation ownership, epics, liveness, and housekeeping. Keep pure models/evaluators independent of I/O and enforce import boundaries. Preserve public API/orchestrator compatibility during extraction. Required tests: architectural dependency rules, no import cycles, focused module tests, startup/shutdown/reload, concurrency and full make test. Acceptance: orchestrator.py becomes a thin composition root; workflow modules have clear single ownership and substantially lower per-file branch complexity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 09:45
---
Direct implementation handoff complete on exact systemic base 689db5160549caa1d126e5de5bf58c0164457c9b. Commit f018dc1fd5b1d86ddf72b63d893e1e52474b433e on branch direct/OOMPAH-798-on-systemic in /home/shedwards/.oompah/worktrees/oompah/OOMPAH-798-direct.LmdyEJ. Extracted authoritative WorkDecision publication/projection, thread-safe event intake/coalescing, and pure immutable fact models from I/O collectors; redirected controllers/evaluators/domain modules to explicit pure boundaries; added ownership design and import-cycle/I/O/complexity/re-export architecture tests. Complexity: root publication 337 LOC/53 branches -> 33/0; coordinator publish 102/10; workflow_facts 1390 LOC -> 856-line collector and 564-line pure model; orchestrator reduced 64283 -> 63795 LOC. Dedicated broker: 146 passed decision/event; 169 passed model/controller/architecture; 98 passed runtime/startup/shutdown/reload/concurrency. Make terminal scan 9/9 and full-tree secret scan passed; diff check and clean worktree passed. Repository-wide broker was queued then cleanly cancelled at integrator request because consolidated exact gate will run once after composition. No push or task-status mutation performed.
---
<!-- COMMENTS:END -->
