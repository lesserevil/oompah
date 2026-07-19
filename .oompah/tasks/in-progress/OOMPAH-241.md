---
id: OOMPAH-241
type: task
status: In Progress
priority: null
title: 'Trickle regression test: release/0.11 backlog with tracker-sourced candidates'
parent: OOMPAH-237
children: []
blocked_by:
- OOMPAH-238
labels: []
assignee: null
created_at: '2026-07-19T02:30:55.182823Z'
updated_at: '2026-07-19T03:56:56.421275Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2b33e4c3-32d9-424f-9400-74e7d6e3763d
---
## Summary

Add a Trickle-specific regression fixture for release/0.11 Release Delivery backlog candidate discovery.

This task depends on OOMPAH-238. Build a deterministic fixture using representative native tracker metadata for a task or epic merged to main but never queued for release/0.11, plus representative release-delivery ledger and ancestry evidence.

Exercise the backlog service or API and verify the merged item appears in the primary needs-delivery list, has a queueable Not selected state, and exposes its source-main commits. Add a companion delivered-by-ancestry case to prove it is excluded from needs-delivery.

Do not depend on live GitHub or the live Trickle checkout.

Acceptance criteria: the regression reproduces the missing-release/0.11-candidate defect before the backend fix and passes after it.
## Context

The bug was discovered on Trickle (the project that uses this oompah instance to manage its own releases). The Trickle release/0.11 backlog was not showing merged tasks because they had never been queued through the delivery ledger. After OOMPAH-238 and OOMPAH-239 are fixed, this regression test proves that the correct data appears and the endpoint doesn't time out.

## Required test

Add a regression test in tests/test_release_delivery_backlog.py or a new file tests/test_release_delivery_backlog_trickle.py:

1. Create a representative fixture of Trickle-scale data:
   - ~200 tracker issues in 'Merged' state with work_branch metadata (e.g., 'OOMPAH-nnn')
   - ~5000 commits enumerated from main (matching realistic Trickle history depth)
   - A target branch 'release/0.11' that exists locally
   - A small delivery ledger (< 20 entries) covering only a subset of the merged tasks

2. The test patches: _acquire_snapshot, _enumerate_commits, tracker.fetch_issues_by_states, _check_ancestry_batch, _is_tracker_only_commit (or its batched replacement)

3. Asserts:
   - get_backlog() completes without raising (no timeout, no unhandled exception)
   - Items derived from tracker records that have no ledger entry appear with state='not_selected'
   - Items with ledger delivery entries have their correct state (open/delivered/etc.)
   - The primary item list is non-empty and does not include non-merged tasks
   - The unassociated_commits count is bounded (< MAX_UNASSOC_TRACKER_ONLY_CHECK or capped)
   - total_commit_count reflects the fixture size

4. Optional: measure wall-clock time to verify it completes within a 30-second bound (use time.monotonic() before/after).

## Acceptance criteria (for this task)
- Trickle-scale regression test passes
- Test demonstrates that previously missing items now appear with 'not_selected' state
- Test demonstrates endpoint completion within time bound
- make test passes

## Files to change
- tests/test_release_delivery_backlog.py or tests/test_release_delivery_backlog_trickle.py — new regression test

## Key references
- tests/test_release_delivery_backlog.py — existing test patterns
- oompah/release_delivery_backlog.py — ItemBacklogService, BacklogResult
- plans/release-delivery-commit-inventory.md — design context

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 03:56
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
