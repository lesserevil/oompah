---
id: OOMPAH-239
type: task
status: In Progress
priority: null
title: 'Fix ItemBacklogService timeout: bound/batch unassociated-commit git operations'
parent: OOMPAH-237
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T02:30:20.650720Z'
updated_at: '2026-07-19T03:30:22.267756Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e8a5d061-7a06-40b8-a1f9-5b2087982fa4
oompah.task_costs:
  total_input_tokens: 90195
  total_output_tokens: 3874
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 90195
      output_tokens: 3874
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 90183
    output_tokens: 545
    cost_usd: 0.0
    recorded_at: '2026-07-19T03:09:49.923632+00:00'
  - profile: standard
    model: unknown
    input_tokens: 12
    output_tokens: 3329
    cost_usd: 0.0
    recorded_at: '2026-07-19T03:12:43.063124+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 03:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 03:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:09
---
Agent completed successfully in 25s (90728 tokens)
---
author: oompah
created: 2026-07-19 03:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 90.2K in / 545 out [90.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 25s
- Log: OOMPAH-239__20260719T030930Z.jsonl
---
author: oompah
created: 2026-07-19 03:09
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-237`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-19 03:10
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 03:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:10
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 13s
- Log: OOMPAH-239__20260719T031037Z.jsonl
---
author: oompah
created: 2026-07-19 03:11
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-19 03:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:12
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-239 is NOT a duplicate. Duplicate screening is complete with no duplicate found.

Candidates reviewed:
- OOMPAH-237 (Open, parent epic): Covers two bugs in the Release Delivery backlog (candidate discovery + timeout). OOMPAH-239 is a child of OOMPAH-237 specifically scoped to Bug 2 (the per-commit git subprocess timeout). Not a duplicate — it is a decomposed child task.
- OOMPAH-238 (In Progress, sibling child): Covers Bug 1 (candidate discovery from tracker Merged records). Distinct scope from OOMPAH-239.
- OOMPAH-240, OOMPAH-241 (Open, sibling children): Dashboard tests and Trickle regression tests respectively. Distinct from OOMPAH-239.
- OOMPAH-236 (Merged): Implemented the item-centric backlog that OOMPAH-237/239 are fixing. Not a duplicate.
- All other merged/archived tasks in .oompah/tasks — no task covers bounding/batching unassociated-commit git operations for the backlog endpoint.

2. Relevant files and evidence:
- oompah/release_delivery_backlog.py — ItemBacklogService.get_backlog() step 7 (unassociated_rows loop) is where _is_tracker_only_commit() is called per commit
- oompah/release_delivery_inventory.py — _is_tracker_only_commit() spawns git diff-tree subprocess per commit; this is the root cause
- tests/test_server_release_delivery_backlog.py — add API regression test for large synthetic commit set
- tests/test_release_delivery_backlog.py — add unit test for bounded git calls

3. Remaining work (from task description):
- Add MAX_UNASSOC_TRACKER_ONLY_CHECK constant and cap calls to _is_tracker_only_commit to first N unassociated commits
- OR batch diff-tree calls into a single subprocess invocation
- Ensure unassociated diagnostics do not delay primary item list construction
- Consider lazy/async computation or total execution-time bound with unassoc_truncated flag
- Add API regression test: large synthetic commit set, mock _is_tracker_only_commit, assert call count bounded, assert primary item list non-empty
- Run make test to verify

4. Recommended next focus: feature (backend implementation in release_delivery_backlog.py + tests)
---
author: oompah
created: 2026-07-19 03:12
---
Agent completed successfully in 90s (3341 tokens)
---
author: oompah
created: 2026-07-19 03:12
---
Run #3 [attempt=3, profile=standard, role=standard -> Claude/default]
- Turns: 23, Tool calls: 15
- Tokens: 12 in / 3.3K out [3.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 30s
- Log: OOMPAH-239__20260719T031118Z.jsonl
---
author: oompah
created: 2026-07-19 03:12
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-19 03:27
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 03:27
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-19 03:30
---
Understanding & Plan (Test Engineer)

Root cause confirmed: oompah/release_delivery_backlog.py step 7 (build unassociated rows) calls _is_tracker_only_commit() for EVERY unassociated commit — each spawns a git diff-tree subprocess. With thousands of unassociated commits on Trickle release/0.11, this causes an HTTP timeout.

Two call sites to address:
1. Step 6 (item rows, L532-534): calls _is_tracker_only_commit per commit per item — bounded by _max_items (500) so less critical
2. Step 7 (unassociated rows, L605): calls _is_tracker_only_commit for ALL unassociated commits — the primary bottleneck

Plan:
- Add MAX_UNASSOC_TRACKER_ONLY_CHECK = 50 constant to release_delivery_backlog.py
- Cap step 7's loop: only call _is_tracker_only_commit for first N unassociated commits; default tracker_only=False beyond the cap
- Export the constant for tests to assert against
- Add regression tests that count git subprocess calls for large synthetic commit sets
- Add coverage that primary item rows are returned even with large unassociated sets
- Run make test to confirm all pass
---
<!-- COMMENTS:END -->
