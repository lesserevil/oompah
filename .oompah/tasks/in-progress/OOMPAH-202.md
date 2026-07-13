---
id: OOMPAH-202
type: task
status: In Progress
priority: 1
title: Run end-to-end release delivery migration and regression coverage
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-194
- OOMPAH-195
- OOMPAH-196
- OOMPAH-198
- OOMPAH-199
- OOMPAH-200
- OOMPAH-201
labels: []
assignee: null
created_at: '2026-07-13T19:33:31.162292Z'
updated_at: '2026-07-13T23:09:07.397092Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 433edd69-2976-4455-b7f4-cb09ee85039a
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md section 7.

Create integration coverage that exercises the released feature across ledger migration, task/epic compatibility, direct commit selection, queue/executor behavior, PR evidence, and inventory rendering. This is the final verification task; do not add product behavior except narrowly scoped test-harness fixes.

Acceptance criteria
- A migrated existing task/epic delivery remains visible and has no duplicate PR after the new UI/API is used.
- A direct main commit can be selected for two release branches, creates two independent ledger deliveries, and does not create a task.
- A merged cherry-pick reports Delivered using source-to-result mapping; a shared-history delivery reports Delivered by ancestry.
- Blocked, retry, archived, unavailable-target, source-head-change, and concurrent/idempotent operator scenarios are covered.
- Full make test passes.

Tests
- Add end-to-end tests using temporary Git repositories and mocked SCM/PR operations for all acceptance scenarios above.
- Run make test and attach the exact result to the task handoff.

Dependencies
- OOMPAH-194, OOMPAH-195, OOMPAH-196, OOMPAH-198, OOMPAH-199, OOMPAH-200, and OOMPAH-201.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 23:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 23:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 23:09
---
Duplicate investigation complete: OOMPAH-202 is NOT a duplicate. All sibling tasks (OOMPAH-193 through OOMPAH-201) cover distinct implementation pieces — ledger schema, migration, queue/executor refactoring, task/epic compat, inventory service, GET API, POST API, UI overlay, and docs/deprecation. No existing task creates end-to-end integration tests using real temporary git repositories. The existing tests are unit/server tests with mocked stores and fake git subprocess calls.

Understanding and plan: OOMPAH-202 is the final verification task. All dependency tasks are Done and their code is on branch epic-OOMPAH-192. I will write tests/test_release_delivery_e2e.py covering: (1) migrated task/epic delivery visible with no duplicate PR; (2) direct main commit selected for two release branches → two independent ledger deliveries, no task created; (3) merged cherry-pick → Delivered via source-to-result mapping; shared-history → Delivered by ancestry; (4) blocked/retry/archived/unavailable-target/source-head-change/concurrent/idempotent scenarios. Tests use real temporary git repos via subprocess and mock the SCM/PR layer only. Then run make test and attach the result.
---
<!-- COMMENTS:END -->
