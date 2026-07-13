---
id: OOMPAH-193
type: task
status: In Progress
priority: 1
title: Add project-owned release delivery ledger
parent: OOMPAH-192
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:31:36.808036Z'
updated_at: '2026-07-13T20:08:44.208642Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 05bfaf18-2b31-4e14-ae2b-5052ca537d9f
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md sections 3.1 and 5.

Implement a versioned .oompah/release-deliveries.yml ledger and a dedicated store module. Define a ReleaseDelivery record with immutable source fields (source branch, source kind, optional source identifier, ordered full source commits, target branch) and mutable execution evidence/lifecycle fields. Reuse the existing release-addendum lifecycle vocabulary, but do not read or write task YAML metadata in this store. Ensure the native tracker writer can atomically persist the ledger on the project default branch.

Acceptance criteria
- Ledger schema and store are documented in code and validate version, ID, full SHA format, enum values, target branch, and source-kind/source-identifier invariants.
- Immutable fields cannot be changed by lifecycle updates.
- Append, lookup by ID, lookup by source identifier, and update operations are atomic under a project-level lock.
- Missing ledger is treated as an empty version-1 ledger; malformed ledgers fail with actionable errors and are never overwritten.

Tests
- Unit tests cover round-trip parsing, missing/malformed/version-mismatched files, invalid entries, immutable-field protection, lookup behavior, and concurrent update locking.
- Use a temporary native repository fixture and verify the ledger write is committed through the supported tracker/git path.

Out of scope
- Migrating old addendums, queue integration, APIs, and UI.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 20:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 20:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 20:04
---
Duplicate investigation complete: no duplicate found. OOMPAH-195 references the same plan sections (3.1 and 5) but is a downstream consumer task (blocked by OOMPAH-193, not a copy). All other release-delivery tasks (194, 196-202) cover distinct phases of the same epic. OOMPAH-193 is unique and foundational - proceeding with implementation.

Plan: Implement the .oompah/release-deliveries.yml ledger schema, ReleaseDelivery dataclass, and ReleaseDeliveryStore module. Key deliverables: immutable source fields, mutable lifecycle/evidence fields, atomic CRUD under project-level lock, version validation, native tracker writer integration, and full unit test coverage.
---
author: oompah
created: 2026-07-13 20:08
---
Discovery complete. Key findings:

1. AddendumStatus enum and VALID_TRANSITIONS in release_addendum_schema.py should be REUSED for the delivery lifecycle (plan says 'reuse existing vocabulary').

2. OompahMarkdownTracker has _atomic_write, _commit_and_push, _prepare_default_branch_for_write, _sync_from_remote — all the git infrastructure. Need to add a write_and_commit_ledger_file method to commit the non-task ledger file via the same path.

3. Module-level lock pattern from release_addendum_queue.py (_source_locks dict + guard) is the right model for the project-level delivery lock.

4. LEDGER_PATH = .oompah/release-deliveries.yml, LEDGER_VERSION = 1, full SHA = 40 hex chars.

Implementation plan:
- oompah/release_delivery_store.py: SourceKind enum, ReleaseDelivery dataclass (immutable source + mutable lifecycle fields), ReleaseDeliveryLedger, LedgerParseError/ImmutableFieldError/DeliveryNotFoundError, module-level project locks, ReleaseDeliveryStore with append/lookup_by_id/lookup_by_source_identifier/update
- oompah/oompah_md_tracker.py: add write_and_commit_ledger_file()
- tests/test_release_delivery_store.py: comprehensive coverage per acceptance criteria
---
<!-- COMMENTS:END -->
