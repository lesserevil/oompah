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
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T02:30:55.182823Z'
updated_at: '2026-07-19T04:03:16.445963Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9441a5f4-276b-4d6d-b259-0ecf94535050
oompah.task_costs:
  total_input_tokens: 90168
  total_output_tokens: 5900
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 90168
      output_tokens: 5900
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 90150
    output_tokens: 606
    cost_usd: 0.0
    recorded_at: '2026-07-19T03:57:22.580057+00:00'
  - profile: standard
    model: unknown
    input_tokens: 18
    output_tokens: 5294
    cost_usd: 0.0
    recorded_at: '2026-07-19T03:59:54.709109+00:00'
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
author: oompah
created: 2026-07-19 03:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:57
---
Agent completed successfully in 27s (90756 tokens)
---
author: oompah
created: 2026-07-19 03:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 90.2K in / 606 out [90.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 27s
- Log: OOMPAH-241__20260719T035704Z.jsonl
---
author: oompah
created: 2026-07-19 03:57
---
Agent completed without closing this issue (27s (90756 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-19 03:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 03:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:59
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-241 is NOT a duplicate. Duplicate screening is complete with no duplicate found.

Candidates reviewed:
- OOMPAH-237 (Open, parent epic): Describes OOMPAH-241 as a child task in its children list. OOMPAH-241 is a decomposed child, not a duplicate of it.
- OOMPAH-238 (Done, sibling): Backend algorithm fix — tracker-sourced candidate discovery in release_delivery_backlog.py. OOMPAH-238 comments explicitly called out OOMPAH-241 as 'Sibling child task for Trickle regression test... Different scope (integration fixture, not backend logic).'
- OOMPAH-239 (Done, sibling): Timeout/performance fix. Comments: 'OOMPAH-240, OOMPAH-241 (Open, sibling children): Dashboard tests and Trickle regression tests respectively. Distinct from OOMPAH-239.'
- OOMPAH-240 (Done, sibling): Dashboard UI tests. Comments: 'OOMPAH-241 (Open, sibling): Trickle-specific regression fixture at service/API level. Different test layer — integration/API fixture, not dashboard JS/UI tests.'
- No archived, done, or merged task covers: building a Trickle-specific regression fixture using native tracker metadata for release/0.11 backlog candidate discovery.

2. Relevant files and evidence:
- oompah/release_delivery_backlog.py — ItemBacklogService.get_backlog(), tracker-sourced discovery at line 450 (OOMPAH-238 fix already in place)
- oompah/release_delivery_inventory.py — _find_branch_commits_in_main() at line 655, resolves work_branch commits reachable from main
- tests/test_release_delivery_backlog.py — 6 new tracker-sourced tests added by OOMPAH-238 (test_merged_task_no_ledger_appears_as_not_selected, etc.); pattern uses _patch_and_run helper
- tests/test_server_release_delivery_backlog.py — server-level tests with BacklogResult, ItemRow, SourceCommitInfo shapes
- The blocker (OOMPAH-238) is Done.

3. Remaining work / risks:
- Build a deterministic integration fixture using native oompah_md tracker metadata (a representative task or epic with merged state, work_branch, and no release delivery ledger entry for release/0.11)
- Fixture must include: tracker issue with merged state + work_branch, release-delivery ledger entries showing the item was never queued for release/0.11, ancestry evidence (for companion 'delivered-by-ancestry' case), and a synthetic git graph (using _find_branch_commits_in_main mock or a real git dir)
- Verify: merged item appears in needs_delivery list with state=not_selected and exposes source-main commits
- Companion case: item delivered by ancestry is excluded from needs_delivery
- Must NOT call live GitHub or live Trickle checkout
- Key risk: _find_branch_commits_in_main calls git subprocesses; test must mock or use a controlled git repo fixture. Existing test pattern in test_release_delivery_backlog.py patches _find_branch_commits_in_main directly.

4. Recommended next focus: test (implement the regression fixture in tests/test_release_delivery_backlog.py or tests/test_server_release_delivery_backlog.py, following existing mock patterns)
---
author: oompah
created: 2026-07-19 03:59
---
Agent completed successfully in 127s (5312 tokens)
---
author: oompah
created: 2026-07-19 03:59
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 37, Tool calls: 27
- Tokens: 18 in / 5.3K out [5.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 7s
- Log: OOMPAH-241__20260719T035752Z.jsonl
---
author: oompah
created: 2026-07-19 04:00
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-19 04:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 04:00
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-19 04:00
---
Understanding & Plan: Implementing Trickle-specific regression fixture for release/0.11 backlog candidate discovery.

Plan:
1. Read existing tests in test_release_delivery_backlog.py to understand mock patterns
2. Read the backlog service code to understand the data flow
3. Build fixture with: (a) a representative oompah_md task with merged state + work_branch, (b) no release/0.11 ledger entry, (c) ancestry evidence for companion case
4. Add regression tests: needs-delivery case (not_selected), delivered-by-ancestry exclusion case
5. Verify tests fail before fix (by temporarily reverting logic) and pass after

Key files from prior investigation:
- oompah/release_delivery_backlog.py (ItemBacklogService.get_backlog, tracker-sourced discovery ~line 450)
- oompah/release_delivery_inventory.py (_find_branch_commits_in_main ~line 655)
- tests/test_release_delivery_backlog.py (existing patterns with _patch_and_run helper)
- tests/test_server_release_delivery_backlog.py (server-level tests)
---
author: oompah
created: 2026-07-19 04:03
---
Discovery: Confirmed code structure and test patterns.

Key findings:
- release_delivery_backlog.py:get_backlog() handles tracker-sourced discovery (OOMPAH-238 fix is present at ~line 310+)
- Tracker-sourced discovery: tracker.fetch_issues_by_states(['Merged']) → _find_branch_commits_in_main() → adds item with not_selected state
- Ancestry detection at step 4: sha in ancestry_set → _compute_cell returns delivered → excluded from needs_delivery
- _aggregate_cell_for_item uses STATUS_RANK (not_selected=1, delivered=3) — delivery beats not_selected, ancestry beats not_selected
- Existing tests use generic release/1.1 and TASK-XX identifiers. OOMPAH-241 needs release/0.11 + oompah_md-style OOMPAH-XXX identifiers
- work_branch in oompah_md tracker = task identifier directly (e.g. 'OOMPAH-215')
- Tests follow _patch_and_run pattern with 5 mock patches (snapshot, commits, ancestry, is_tracker_only, find_branch_commits_in_main)

Plan: Add TestTrickleRelease011BacklogRegression class with:
1. Primary regression: OOMPAH-215 merged/never queued for release/0.11 → appears as not_selected
2. Companion ancestry: OOMPAH-215 already on release/0.11 → state=delivered, excluded from needs-delivery
3. Supporting tests: multi-commit, epic type, ledger-other-branch isolation, needs_delivery filter
---
<!-- COMMENTS:END -->
