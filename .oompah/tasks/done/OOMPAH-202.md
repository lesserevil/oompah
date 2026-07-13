---
id: OOMPAH-202
type: task
status: Done
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
updated_at: '2026-07-13T23:25:23.834466Z'
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
author: oompah
created: 2026-07-13 23:24
---
Implementation complete. Created tests/test_release_delivery_e2e.py with 37 end-to-end integration tests using real temporary git repositories and mocked SCM/PR operations.

Tests cover all acceptance criteria:

1. Migration & compatibility (6 tests): task/epic addendums migrate to ledger; visible via DualReadDeliveryAdapter; re-approval skips active pairs (no duplicate PR); malformed OOMPAH-183 sentinel SHAs skipped; adapter deduplicates by migrated_from.

2. Direct commit selection (3 tests): source_kind=commits delivery for two branches; independent; no task records created.

3. Delivery evidence (5 tests): merged cherry-pick → Delivered with evidence=delivery (source-to-result mapping); shared-history commit → Delivered with evidence=ancestry; not_selected when no evidence; active delivery beats ancestry.

4. Blocked/retry/archived/unavailable-target (6 tests): unavailable target → blocked without cherry-picking; blocked → open retry; open/blocked → archived; archived does not block re-approval; inventory shows archived state.

5. Source-head change (1 test): stale cursor raises SourceChangedError.

6. Concurrent/idempotent (4 tests): concurrent appends same delivery_id → one success; concurrent queue claim → one winner; scan skips archived; deduplication prevents double-append.

7. Full pipeline with mocked SCM (5 tests): real cherry-pick to real worktree; push/PR mocked; in_review + result_commits persisted; PR merge → merged; closed unmerged PR → retryable in_review; conflict → blocked; full pipeline migration→in_progress→merged→inventory.

8. PR evidence in inventory (4 tests): in_review state visible; multi-branch independent columns; task association shown; commits-kind has no association.

9. Filter/pagination (3 tests): needs_delivery excludes ancestry-delivered; all includes them; pagination across pages.
---
author: oompah
created: 2026-07-13 23:25
---
Verification: make test result — 8838 passed, 28 skipped, 0 failures in 115.08s.

The 37 new e2e tests in tests/test_release_delivery_e2e.py pass cleanly. No regressions introduced.

All 5 acceptance criteria confirmed:
✓ Migrated existing task/epic delivery remains visible; no duplicate PR after re-approval.
✓ Direct main commit selected for two release branches → two independent ledger deliveries, no task created.
✓ Merged cherry-pick reports Delivered using source-to-result mapping (evidence=delivery); shared-history delivery reports Delivered by ancestry (evidence=ancestry).
✓ Blocked, retry, archived, unavailable-target, source-head-change, and concurrent/idempotent scenarios covered.
✓ Full make test passes: 8838 passed, 28 skipped, 0 failures.
---
author: oompah
created: 2026-07-13 23:25
---
Completion: OOMPAH-202 delivered.

Added tests/test_release_delivery_e2e.py (1694 lines, 37 tests) as the final verification layer for the release delivery feature. Tests are end-to-end: real temporary git repositories created via subprocess, SCM/PR operations mocked at the push_branch/scm.create_review layer only.

No product behavior added — tests only, as specified. All dependency work (OOMPAH-193 through OOMPAH-201) was already Done and covered by the e2e tests.

Branch epic-OOMPAH-192 pushed and up to date with origin.
---
author: oompah
created: 2026-07-13 23:25
---
Added tests/test_release_delivery_e2e.py (37 e2e tests) covering all acceptance criteria: migration/compatibility, direct commit selection, cherry-pick vs ancestry evidence, blocked/retry/archived/unavailable-target/source-head-change/concurrent scenarios, full pipeline with mocked SCM/PR. make test: 8838 passed, 28 skipped, 0 failures.
---
<!-- COMMENTS:END -->
