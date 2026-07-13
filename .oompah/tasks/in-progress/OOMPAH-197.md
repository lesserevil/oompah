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
updated_at: '2026-07-13T21:51:10.965473Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 96e398fe-83b7-4f05-a2c5-a6a8057ddaa2
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 21:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 21:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 21:51
---
Duplicate investigation complete: OOMPAH-197 is unique. No other task implements CommitInventoryService. It is specifically child 5 of OOMPAH-192 epic; other siblings address ledger (193), migration (194/195), compat (196), API endpoint (198), queue API (199), UI (200/201), e2e (202). Proceeding with implementation.

Plan: Implement oompah/release_delivery_inventory.py — CommitInventoryService with:
1. git ls-remote fetch of source+release refs with 60s TTL cache per (project_id, sorted_branch_set)
2. git rev-list --topo-order --no-merges for non-merge commit enumeration
3. Opaque base64 JSON cursors containing (source_head, last_sha) — reject on source_head change
4. §2.3 status precedence: active delivery → merged delivery → ancestry → archived → not_selected
5. git merge-base --is-ancestor batched per release branch
6. Stale flag when falling back from remote fetch failure to local refs/remotes/origin/*
7. filter=needs_delivery / all-commits, text search, branch subset filtering, bounded page size
8. Source task/epic association enrichment only from ledger source_identifier (no subject guessing)
9. Cache invalidate() method for push webhook / delivery lifecycle update triggers
---
<!-- COMMENTS:END -->
