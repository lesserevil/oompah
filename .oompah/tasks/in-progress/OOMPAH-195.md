---
id: OOMPAH-195
type: task
status: In Progress
priority: 1
title: Move release queue and executor identity to ledger delivery IDs
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-193
labels: []
assignee: null
created_at: '2026-07-13T19:31:43.705145Z'
updated_at: '2026-07-13T20:37:10.891445Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b52ee329-6816-46c5-9d64-56a19aa89830
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md sections 3.1 and 5.

Refactor the release-addendum queue, lease handling, executor, retry, archive, PR reconciliation, and worktree cleanup to consume a ReleaseDelivery ledger ID. Preserve the existing cherry-pick and PR workflow. The executor must use the immutable ordered source_commits snapshot and write work branch, PR URL/number, result commit SHAs, timestamps, errors, and lifecycle transitions only through the ledger.

Acceptance criteria
- Queue claim/release/retry/lease-expiry behavior is keyed by delivery ID and survives a service restart.
- A multi-commit delivery cherry-picks in stored order and records target result SHAs before entering In review.
- PR merge reconciliation marks the exact delivery Merged; a closed-unmerged PR can be retried without changing source commits.
- An unavailable/deleted target is not executed and receives an actionable Blocked error.

Tests
- Update queue and executor unit tests to use ledger fixtures.
- Add coverage for restart recovery, expired lease, multi-commit ordering, result-SHA persistence, retry, archive, and unavailable-target refusal.

Dependencies
- OOMPAH-193.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 20:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 20:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
