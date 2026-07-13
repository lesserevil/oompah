---
id: OOMPAH-194
type: task
status: Done
priority: 1
title: Migrate legacy release addendums into the delivery ledger
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-193
labels: []
assignee: null
created_at: '2026-07-13T19:31:40.173681Z'
updated_at: '2026-07-13T20:36:54.945662Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 107a39ef-02ce-4ed0-873a-634c41dfb495
oompah.task_costs:
  total_input_tokens: 101
  total_output_tokens: 2326
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 101
      output_tokens: 2326
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 101
    output_tokens: 2326
    cost_usd: 0.0
    recorded_at: '2026-07-13T20:36:48.108303+00:00'
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md section 3.2.

Implement an idempotent migration from source-task oompah.release_addendums metadata into .oompah/release-deliveries.yml. Build a dual-read adapter so callers see a single de-duplicated delivery view while older metadata remains present. Preserve source commits, source task/epic identity, target, lifecycle status, work branch, PR evidence, result commits, errors, timestamps, and a migrated_from legacy ID.

Acceptance criteria
- Migration scans all project tasks and epics, including terminal items, and creates exactly one ledger record per legacy addendum.
- Re-running the migration produces no duplicate records and no unnecessary commit.
- Dual reads de-duplicate migrated legacy records by migrated_from and preserve all history.
- A malformed legacy record is reported and skipped without preventing unrelated valid records from migrating.

Tests
- Fixtures cover task and epic addendums in every lifecycle state, duplicate/missing IDs, malformed legacy records, and a second migration run.
- Verify migrated records preserve all execution evidence byte-for-byte where schema permits.

Dependencies
- OOMPAH-193.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 20:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 20:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 20:25
---
Duplicate investigation complete: no duplicate found. OOMPAH-194 is a distinct step in the OOMPAH-192 epic. OOMPAH-193 (the foundational ledger store) is in-progress and its code is already present on the branch. OOMPAH-194 is unique.

Proceeding with implementation. Plan:

1. oompah/release_addendum_migration.py — idempotent migration scanning all tasks/epics (including terminal) for oompah.release_addendums metadata, building ReleaseDelivery records with migrated_from set to the legacy addendum ID, and appending to the ledger store. SHA validation gates admission: addendums with non-SHA sentinel commits (e.g. 'migration-pending' from OOMPAH-183) are reported and skipped.

2. oompah/release_delivery_adapter.py — DualReadDeliveryAdapter that combines ledger entries (via ReleaseDeliveryStore.lookup_by_source_identifier) with legacy task-metadata addendums, deduplicating by migrated_from. Non-migrated legacy addendums are converted to ReleaseDelivery on-the-fly for a single unified view.

3. tests/test_release_addendum_migration.py and tests/test_release_delivery_adapter.py — fixtures covering all lifecycle states, duplicates, malformed records, and second migration run; byte-for-byte evidence preservation verified.
---
author: oompah
created: 2026-07-13 20:35
---
Implementation complete. Created two new modules:

1. oompah/release_addendum_migration.py — idempotent migration that scans all project tasks and epics (including terminal) for oompah.release_addendums metadata and appends them to the delivery ledger. Key design: (a) reads the ledger once at start to build migrated_from set for O(1) idempotency checks; (b) validates every commit as a full 40-char hex SHA — addendums with OOMPAH-183 sentinel values are reported as skipped_malformed; (c) each structural parse failure skips only that entry without blocking others; (d) store append failures increment errors without aborting the rest; (e) no write occurs when nothing changes.

2. oompah/release_delivery_adapter.py — DualReadDeliveryAdapter that combines ledger entries (lookup_by_source_identifier) with legacy oompah.release_addendums metadata. Deduplication: ledger entries with migrated_from matching a legacy addendum.id shadow the legacy record. Non-migrated legacy addendums appear as synthetic ReleaseDelivery objects with id='legacy:<addendum-id>'. Provides list_deliveries_for_source() and list_all_deliveries().
---
author: oompah
created: 2026-07-13 20:35
---
Verification: all 137 new tests pass (75 migration + 62 adapter). Full suite: 8257 passed, 28 skipped, 0 failures. Tests cover task/epic addendums in every lifecycle state, duplicate/missing IDs, malformed legacy records, second migration run (idempotency), partial migration resumption, byte-for-byte evidence preservation, and error isolation.
---
author: oompah
created: 2026-07-13 20:36
---
Completion: Branch pushed and all tests passing (8257 total, 137 new). Delivered:

- oompah/release_addendum_migration.py: idempotent migration (OOMPAH-183 sentinels safely skipped, partial runs resumable, no unnecessary writes on second run)
- oompah/release_delivery_adapter.py: DualReadDeliveryAdapter with de-duplication by migrated_from
- tests/test_release_addendum_migration.py: 75 tests covering all acceptance criteria
- tests/test_release_delivery_adapter.py: 62 tests

All acceptance criteria met: migration scans terminal items, exactly one record per addendum, re-run is a no-op, dual reads de-duplicate by migrated_from, malformed records are reported and skipped without blocking others.
---
author: oompah
created: 2026-07-13 20:36
---
Implemented idempotent migration from oompah.release_addendums metadata into .oompah/release-deliveries.yml (release_addendum_migration.py) and DualReadDeliveryAdapter for unified de-duplicated delivery view (release_delivery_adapter.py). Full test coverage in 137 new tests. All acceptance criteria met.
---
author: oompah
created: 2026-07-13 20:36
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 65
- Tokens: 101 in / 2.3K out [2.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 0s
- Log: OOMPAH-194__20260713T201956Z.jsonl
---
<!-- COMMENTS:END -->
