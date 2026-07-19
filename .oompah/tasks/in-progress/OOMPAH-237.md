---
id: OOMPAH-237
type: task
status: In Progress
priority: null
title: Fix Release Delivery backlog candidate discovery and timeout
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-19T02:22:21.578496Z'
updated_at: '2026-07-19T02:24:05.907819Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f667144c-87e3-471b-9aa4-03f12d1d61f5
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
<!-- COMMENTS:END -->
