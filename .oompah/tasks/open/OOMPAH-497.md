---
id: OOMPAH-497
type: task
status: Open
priority: 2
title: Assign canonical ownership for overlapping Release Delivery UI tests
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:53:32.426575Z'
updated_at: '2026-07-28T16:10:03.273690Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 08a58dd5-cb91-470f-82aa-6a0afbb82743
oompah.work_branch: epic-OOMPAH-490
oompah.task_costs:
  total_input_tokens: 17
  total_output_tokens: 4238
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 17
      output_tokens: 4238
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 17
    output_tokens: 4238
    cost_usd: 0.0
    recorded_at: '2026-07-28T16:09:58.845853+00:00'
---
## Summary

Implementation scope

Map and remove cross-file duplication among `tests/test_dashboard_release_delivery_ui.py`, `tests/test_release_delivery_page.py`, and `tests/test_dashboard_release_addendums_ui.py`. Treat `test_release_delivery_page.py` as the owner of dedicated-page navigation, page structure, URL state, bootstrap, accessibility, and live-status contracts. Treat `test_dashboard_release_addendums_ui.py` as the owner of add-release-branches dialog controls. Remove the same-named or equivalent copies from `test_dashboard_release_delivery_ui.py`, including the retained-controls assertions already covered by the addendums suite. Update stale module/class docstrings that still call the dedicated page an overlay. Do not yet collapse unique backlog rendering, selection, queuing, status, drawer, XSS, or refresh behavior; that belongs to the dependent task.

Tests

Create a short contract-ownership table in a comment at the top of the surviving legacy-named file, listing each category and canonical test module. Run all three files before and after and record collection counts. Search for duplicate test names across these files and justify any remaining collision. Run `make test` after safety isolation.

Acceptance criteria

Each page/dialog contract has one clear owner, at least the 12 same-named page contracts and five exact retained-control duplicates are removed or merged, module descriptions match the dedicated-page architecture, and all three focused suites pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 16:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:08
---
Agent failed: errored. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-28 16:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/fable]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 13s
- Log: OOMPAH-497__20260728T160757Z.jsonl
---
author: oompah
created: 2026-07-28 16:08
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 16:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:09
---
Understanding: Screening OOMPAH-497 for duplicates before any implementation. The task targets cross-file duplication among tests/test_dashboard_release_delivery_ui.py, tests/test_release_delivery_page.py, and tests/test_dashboard_release_addendums_ui.py to assign canonical ownership of page/navigation/accessibility contracts vs. dialog controls. I will search task records and project documentation for any prior equivalent work before proceeding.
---
author: oompah
created: 2026-07-28 16:09
---
Discovery: No duplicate confirmed. Searched .oompah/tasks (archived, backlog, open, merged) and docs/plans/README.md/WORKFLOW.md for: release_delivery, test_release_delivery, canonical ownership, addendums, overlapping tests. No existing task matches OOMPAH-497's specific scope of mapping and removing cross-file duplication among these three UI test files and establishing module-level ownership.

Closest tasks reviewed:
- OOMPAH-490 (parent epic): assigns OOMPAH-497 uniquely as the canonical-ownership step; OOMPAH-498 explicitly depends on OOMPAH-497 completing first ('After canonical ownership is established...')
- OOMPAH-498: a FOLLOW-UP task (Open) that groups granular assertions after ownership is set — distinct scope, not a duplicate
- OOMPAH-496: consolidates draft-epic/epic-strategy UI files — different files entirely
- OOMPAH-499: removes exact duplicates and resolves Python name shadowing — different scope (no ownership categorization)
- OOMPAH-495: retired pre-implementation state-branch design tests — different scope

The three target files (test_dashboard_release_delivery_ui.py, test_release_delivery_page.py, test_dashboard_release_addendums_ui.py) all exist in tests/. OOMPAH-497 is the unique task in the epic that establishes the ownership boundary between them.
---
author: oompah
created: 2026-07-28 16:09
---
Focus handoff: duplicate_detector

1. Outcome: No confirmed duplicate. OOMPAH-497 should proceed to implementation.

2. Evidence: Exhaustively searched .oompah/tasks (all subdirectories), docs, plans, README.md, and WORKFLOW.md for 'release_delivery', 'addendums', 'canonical', 'overlapping.*test', 'delivery.*ui', 'delivery.*page'. Read OOMPAH-490, OOMPAH-491, OOMPAH-495, OOMPAH-496, OOMPAH-498, OOMPAH-499 in full. All three target test files confirmed present in tests/. OOMPAH-498 explicitly depends on this task's canonical ownership being established first.

3. Remaining work / risks:
   - Record baseline collection counts from all three files before changes
   - Move/remove the 12 same-named page contracts from test_dashboard_release_delivery_ui.py (owned by test_release_delivery_page.py)
   - Remove the 5 retained-controls duplicates covered by test_dashboard_release_addendums_ui.py
   - Update stale 'overlay' docstrings to 'dedicated page'
   - Add contract-ownership table comment at top of test_dashboard_release_delivery_ui.py
   - Run make test; record before/after counts

4. Recommended next focus: test (or refactor) — implementation of the canonical-ownership consolidation in the three test files.
---
author: oompah
created: 2026-07-28 16:10
---
Agent completed successfully in 97s (4255 tokens)
---
author: oompah
created: 2026-07-28 16:10
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 32, Tool calls: 23
- Tokens: 17 in / 4.2K out [4.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 37s
- Log: OOMPAH-497__20260728T160823Z.jsonl
---
author: oompah
created: 2026-07-28 16:10
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
