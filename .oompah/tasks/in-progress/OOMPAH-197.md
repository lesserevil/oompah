---
id: OOMPAH-197
type: task
status: In Progress
priority: 1
title: Build the default-branch commit inventory service
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-193
labels: []
assignee: null
created_at: '2026-07-13T19:32:47.560323Z'
updated_at: '2026-07-13T21:49:10.260268Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md section 4.1.

Implement CommitInventoryService as a synchronous, independently testable module. Given one project, configured release lines, cursor, search/filter, and limit, return non-merge commits reachable from the default branch in newest-first topological order plus per-release delivery status. Use immutable source/release ref snapshots, ledger evidence first, and Git ancestry second. Do not guess task ownership from commit subjects.

Acceptance criteria
- Enumerates only non-merge commits reachable from origin/default_branch; squash commits remain selectable.
- Uses opaque cursors tied to source HEAD and rejects a cursor when source HEAD changes.
- Computes delivery state precedence exactly as plan section 2.3, including source-to-result SHA mappings for cherry-picks.
- Supports needs_delivery, all-commits, text search, branch subsets, bounded page size, and stale fallback labeling.
- Caches completed project/ref-set snapshots for 60 seconds and exposes invalidation.

Tests
- Temporary Git-repository fixtures cover ordering, pagination, source-head change, merge/squash behavior, ancestry delivery, ledger delivery, active delivery, archived delivery, and no evidence.
- Tests cover remote-ref failure/local-ref fallback and ensure no fabricated release branch.

Dependencies
- OOMPAH-193.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

