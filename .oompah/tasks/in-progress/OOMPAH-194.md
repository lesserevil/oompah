---
id: OOMPAH-194
type: task
status: In Progress
priority: 1
title: Migrate legacy release addendums into the delivery ledger
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-193
labels: []
assignee: null
created_at: '2026-07-13T19:31:40.173681Z'
updated_at: '2026-07-13T20:19:52.169951Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 107a39ef-02ce-4ed0-873a-634c41dfb495
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
<!-- COMMENTS:END -->
