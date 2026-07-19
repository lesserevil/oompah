---
id: OOMPAH-237
type: task
status: In Progress
priority: null
title: Fix Release Delivery backlog candidate discovery and timeout
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-19T02:22:21.578496Z'
updated_at: '2026-07-19T02:25:48.878950Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8b5b1268-7598-4792-8044-c26745cada01
oompah.task_costs:
  total_input_tokens: 91190
  total_output_tokens: 678
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 91190
      output_tokens: 678
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 91190
    output_tokens: 678
    cost_usd: 0.0
    recorded_at: '2026-07-19T02:24:05.218347+00:00'
---
## Summary

Problem
OOMPAH-236 implemented an item-centric Release Delivery backlog, but it derives task/epic association only from existing release-delivery ledger entries. This excludes the exact items the UI must surface: tasks and epics merged to main that have never been queued for a release branch. They are incorrectly treated as unassociated commits and omitted from the primary backlog.

The endpoint also times out on Trickle because it performs expensive per-commit Git checks while building the unassociated-commit diagnostic section.

Required implementation
- Derive primary backlog candidates from native tracker records for tasks and epics that have individually merged to the project default branch, using durable merge evidence (merged PR metadata, merge commit SHA, or equivalent existing tracker metadata). Do not require a prior release-delivery ledger entry.
- Resolve each candidate item to its associated source-main commit set. Include only commits reachable from origin/<default-branch>.
- Use release-delivery ledger records and ancestry checks only to calculate the selected release branch state: not selected, active, blocked, delivered, or archived.
- Continue showing only candidates not delivered to the selected branch when filter=needs_delivery. An item with no previous delivery record must appear as Not selected and be queueable.
- Keep direct-to-main/unassociated commits out of the primary candidate table. If retained as diagnostics, compute them with bounded/batched Git operations and do not let them delay primary backlog rendering.
- Add an explicit execution-time bound/cache strategy so the endpoint returns normally for Trickle-scale history.

Tests
- Unit tests: merged task with no ledger delivery appears as Not selected; merged epic with multiple commits appears once; non-merged task is excluded; ledger and ancestry delivery states override the default state correctly.
- API regression test with a large synthetic commit set proves the primary response does not perform per-commit subprocess calls for unassociated diagnostics and completes within the service timeout.
- Dashboard test: a newly merged task with no release history is visible and queueable for the selected branch.
- Regression test using representative Trickle task metadata and release/0.11 data or fixtures.

Acceptance criteria
- Selecting Trickle release/0.11 shows merged tasks/epics from main that are not yet delivered, including items never previously queued for release delivery.
- The backlog endpoint returns a response instead of timing out.
- No item is promoted to the primary list merely because it has an old ledger entry but lacks valid merged-to-main evidence.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 02:23
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 02:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 02:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 91.2K in / 678 out [91.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 28s
- Log: OOMPAH-237__20260719T022343Z.jsonl
---
author: oompah
created: 2026-07-19 02:24
---
Agent completed successfully in 28s (91868 tokens)
---
author: oompah
created: 2026-07-19 02:24
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-237`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-19 02:24
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 02:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 02:25
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-237 is NOT a duplicate. Duplicate screening is complete with no duplicate found.

Candidates reviewed:
- OOMPAH-236 (Merged): The direct predecessor — implemented the item-centric release delivery backlog that OOMPAH-237 is now bug-fixing. Not a duplicate; OOMPAH-237 is a follow-up fix on delivered OOMPAH-236 work.
- All other tasks searched (in-progress, done, merged, archived directories) — no task covers the two specific bugs described: (a) candidate discovery limited to ledger entries (items merged but never queued are excluded) and (b) endpoint timeout due to per-commit Git operations in the unassociated-commit diagnostic.

2. Relevant files and evidence:
- oompah/release_delivery_backlog.py — the ItemBacklogService added by OOMPAH-236; this is where candidate discovery logic and the unassociated-commit computation live
- oompah/server.py — the GET /api/v1/projects/{project_id}/release-delivery/backlog endpoint
- oompah/templates/dashboard.html — the item-centric dashboard UI
- plans/release-delivery-commit-inventory.md — design doc for the release delivery backlog
- tests/test_release_delivery_backlog.py, tests/test_server_release_delivery_backlog.py, tests/test_dashboard_release_delivery_ui.py — existing tests that need to be extended

3. Remaining work:
- Fix candidate discovery to use native tracker merged PR/merge commit evidence (not just ledger entries), so items merged to main but never queued appear as 'Not selected'
- Add bounded/cached Git operations for unassociated-commit diagnostics to fix timeout
- Add unit tests per the spec (merged task with no ledger entry → Not selected; merged epic with multiple commits → appears once; non-merged task excluded; ledger/ancestry states override)
- API regression test proving no per-commit subprocess calls for unassociated diagnostics
- Dashboard test for newly merged task with no release history being visible and queueable
- Trickle regression test (release/0.11 fixture)

4. Recommended next focus: feature (backend fix to release_delivery_backlog.py + new tests)
---
author: oompah
created: 2026-07-19 02:25
---
Agent completed successfully in 79s (2987 tokens)
---
<!-- COMMENTS:END -->
