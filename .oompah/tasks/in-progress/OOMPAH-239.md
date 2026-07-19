---
id: OOMPAH-239
type: task
status: In Progress
priority: null
title: 'Fix ItemBacklogService timeout: bound/batch unassociated-commit git operations'
parent: OOMPAH-237
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-19T02:30:20.650720Z'
updated_at: '2026-07-19T03:09:23.773973Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7f3b6a5c-6892-41f5-8986-f0965dd6107c
---
## Summary

Remove the Release Delivery backlog timeout caused by per-commit Git subprocess work.

Read first: oompah/release_delivery_backlog.py and the OOMPAH-237 description. The primary task/epic backlog must return without waiting on tracker-only classification for every unassociated main-branch commit.

Replace repeated per-commit Git checks with bounded or batched operations and cache reusable results. Keep unassociated direct-to-main commits diagnostic-only; they must not delay construction of primary item rows. Preserve correct tracker-only classification where it is displayed.

Tests: add a large synthetic commit-set regression test that counts Git calls or enforces a bounded execution path, plus coverage that primary candidate rows are returned when diagnostic commit classification is skipped/deferred.

Acceptance criteria: the Trickle release/0.11 backlog endpoint returns within its HTTP timeout, and the implementation does not issue one subprocess per unassociated commit during primary backlog rendering.
## Problem

When the unassociated-commit diagnostic section is computed, ItemBacklogService calls _is_tracker_only_commit() for each unassociated commit. This function spawns a git diff-tree subprocess per commit. At Trickle scale (thousands of commits on main), this causes the backlog endpoint to time out.

## Required fix

1. Cap the number of unassociated commits for which tracker_only is computed: introduce a MAX_UNASSOC_TRACKER_ONLY_CHECK constant (e.g., 50) — only run _is_tracker_only_commit for the first N unassociated commits; leave tracker_only=False for the rest.

2. Alternatively (or additionally): batch the diff-tree calls into a single git command that processes multiple SHAs in one subprocess invocation, removing the per-commit subprocess overhead.

3. Ensure unassociated-commit diagnostics do NOT delay the primary backlog item list. If unassociated computation is expensive, consider making it lazy or moving it to a separate field with its own timeout/cache.

4. Add an explicit total-execution-time bound: if the backlog service has been running for more than a configurable wall-clock limit (e.g., 25 seconds), truncate the unassociated-commit list early and set an unassoc_truncated=True flag in BacklogResult rather than timing out entirely.

## API regression test required

Add a test in tests/test_server_release_delivery_backlog.py (or tests/test_release_delivery_backlog.py) that:
- Creates a large synthetic commit set (e.g., 5000 unassociated commits)
- Calls get_backlog() with _is_tracker_only_commit mocked to record calls
- Asserts that the number of _is_tracker_only_commit calls is bounded (< MAX_UNASSOC_TRACKER_ONLY_CHECK or 0 if fully batched)
- Asserts that the primary item list is not empty (primary response is unaffected)
- Asserts that the call completes without raising a timeout

## Acceptance criteria (for this task)
- The backlog endpoint returns a response (does not time out) when there are thousands of unassociated commits
- The primary item table is computed before the unassociated-commit section
- Per-commit subprocess calls for unassociated diagnostics are bounded or eliminated
- make test passes

## Files to change
- oompah/release_delivery_backlog.py — bound/batch unassociated diagnostic computation
- tests/test_server_release_delivery_backlog.py — API regression test for large commit set
- tests/test_release_delivery_backlog.py — unit test for bounded git calls

## Key references
- oompah/release_delivery_inventory.py: _is_tracker_only_commit() — the problematic per-commit subprocess
- oompah/release_delivery_backlog.py: ItemBacklogService.get_backlog() step 7 (unassociated_rows loop)

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes
