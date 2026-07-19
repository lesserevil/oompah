---
id: OOMPAH-238
type: task
status: In Progress
priority: null
title: 'Fix ItemBacklogService candidate discovery: derive from tracker Merged records,
  not ledger'
parent: OOMPAH-237
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T02:30:01.408523Z'
updated_at: '2026-07-19T03:10:09.494466Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7b635ff6-28c9-4888-95f5-f80f4b13e9da
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 3202
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 3202
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 10
    output_tokens: 3202
    cost_usd: 0.0
    recorded_at: '2026-07-19T03:09:09.713700+00:00'
---
## Summary

Implement the backend correction for OOMPAH-237.

Read first: oompah/release_delivery_backlog.py, oompah/release_delivery_inventory.py, the native tracker model, and OOMPAH-237.

Replace ledger-only association discovery with tracker-sourced discovery: enumerate tasks and epics that have durable evidence of an individual merge to the default branch, resolve their source merge commit(s), and include only commits reachable from origin/main. A candidate with no release-delivery record must be returned as Not selected for the chosen release branch. Use the ledger and ancestry only for delivery status, not eligibility.

Do not rewrite the delivery ledger or executor. Preserve the separate unassociated direct-commit diagnostic path.

Tests: add focused unit tests for a merged task without ledger history, a merged epic with multiple commits, a non-merged task exclusion, and ledger/ancestry status precedence.

Acceptance criteria: the backend returns a queueable item row for a merged task or epic that has never previously been queued to any release branch; it excludes tracker items lacking merged-to-main evidence.
## Problem

ItemBacklogService.get_backlog() in oompah/release_delivery_backlog.py currently builds its primary candidate list from delivery ledger entries only. The association_by_sha dict is populated from ReleaseDelivery.source_identifier values. Tasks/epics merged to main that have never been queued for release delivery have no ledger entry and therefore never appear in the backlog — they are silently omitted.

## Required fix

Replace the ledger-centric candidate discovery with native tracker record discovery:

1. When a tracker is provided, call tracker.fetch_issues_by_states(['Merged']) to get all tasks and epics that have merged to the project default branch.
2. For each merged issue, resolve its source commits on the default branch using:
   - Issue.work_branch metadata (the branch the agent worked on, stored as oompah.work_branch in issue metadata)
   - Use git to find commits from that work_branch that are reachable from origin/<default_branch> but not from origin/<default_branch> excluding the merge point (e.g., using git log origin/<default_branch> --ancestry-path <work_branch>^..origin/<default_branch> or similar git rev-list technique)
   - Alternatively: match commits by merge commit SHA if it can be derived from review_url/review_number metadata
3. Include only commits that are in the all_commits enumeration (reachable from origin/<default_branch>).
4. Continue using the delivery ledger ONLY for status calculation: use ledger records and ancestry checks to determine not_selected / open / in_progress / blocked / delivered / archived state per item.
5. Items derived from tracker records but with no ledger entry must appear as 'Not selected' — they are queueable.
6. Guard: do NOT promote an item to the primary list if it lacks valid merge evidence (the old behaviour of promoting items solely because they have a ledger entry but no merge evidence must also be removed).

## Acceptance criteria (for this task)
- Merged task with no ledger delivery appears as 'not_selected' in the backlog
- Merged epic whose work spans multiple commits appears exactly once, with all commits listed
- Non-merged task (state != Merged) is excluded from the primary candidate list
- Existing ledger delivery states (open, in_progress, blocked, delivered, archived) correctly override the default 'not_selected' for items that do have ledger entries
- make test passes

## Files to change
- oompah/release_delivery_backlog.py — algorithm changes
- tests/test_release_delivery_backlog.py — add unit tests per spec:
  * test_merged_task_no_ledger_appears_as_not_selected
  * test_merged_epic_multiple_commits_appears_once
  * test_nonmerged_task_excluded
  * test_ledger_state_overrides_default_for_merged_item

## Key references
- oompah/models.py: Issue.work_branch, Issue.issue_type, Issue.state, Issue.review_url
- oompah/oompah_md_tracker.py: fetch_issues_by_states(['Merged'])
- oompah/release_delivery_backlog.py: ItemBacklogService.get_backlog() — current implementation
- tests/test_release_delivery_backlog.py — existing test patterns (mock tracker, delivery store)

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 03:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 03:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 03:08
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-238 is NOT a duplicate. Duplicate screening is complete with no duplicate found.

Candidates reviewed:
- OOMPAH-237 (Open, parent): The parent epic — identifies both the candidate-discovery bug and the timeout bug. OOMPAH-238 is a purposefully decomposed child of OOMPAH-237, not a duplicate of it.
- OOMPAH-239 (Open): Sibling child task covering the timeout/performance fix (bounded git operations). Covers different scope — OOMPAH-238 is about algorithm correctness, OOMPAH-239 is about latency.
- OOMPAH-240 (Open): Sibling child task for dashboard tests; depends on OOMPAH-238. Different scope (UI test layer, not backend logic).
- OOMPAH-241 (Open): Sibling child task for Trickle regression test; depends on OOMPAH-238. Different scope (integration fixture, not backend logic).
- OOMPAH-236 (Merged): The implementation that introduced the bug. Not a duplicate — OOMPAH-238 is a fix for OOMPAH-236's candidate-discovery logic.

2. Relevant files and evidence:
- oompah/release_delivery_backlog.py — ItemBacklogService.get_backlog(); candidate list currently built from ledger entries only
- oompah/release_delivery_inventory.py — delivery ledger data model
- oompah/models.py — Issue.work_branch, Issue.state, Issue.issue_type, Issue.review_url used for tracker-sourced candidate discovery
- oompah/oompah_md_tracker.py — fetch_issues_by_states(['Merged']) method to enumerate merged tracker items
- tests/test_release_delivery_backlog.py — existing test patterns (mock tracker, delivery store)

3. Remaining work:
- Replace ledger-centric candidate discovery with tracker-sourced discovery in ItemBacklogService.get_backlog()
- Add unit tests: test_merged_task_no_ledger_appears_as_not_selected, test_merged_epic_multiple_commits_appears_once, test_nonmerged_task_excluded, test_ledger_state_overrides_default_for_merged_item
- Guard: remove any path that promotes items to primary list without valid merge evidence

4. Recommended next focus: feature (backend Python implementation of the algorithm fix and unit tests)
---
author: oompah
created: 2026-07-19 03:09
---
Agent completed successfully in 77s (3212 tokens)
---
author: oompah
created: 2026-07-19 03:09
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 21, Tool calls: 13
- Tokens: 10 in / 3.2K out [3.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 17s
- Log: OOMPAH-238__20260719T030759Z.jsonl
---
author: oompah
created: 2026-07-19 03:09
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-19 03:10
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
