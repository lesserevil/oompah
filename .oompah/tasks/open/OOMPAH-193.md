---
id: OOMPAH-193
type: task
status: Open
priority: 1
title: Add project-owned release delivery ledger
parent: OOMPAH-192
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:31:36.808036Z'
updated_at: '2026-07-13T20:00:21.568644Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

