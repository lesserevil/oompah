---
id: OOMPAH-195
type: task
status: Backlog
priority: 1
title: Move release queue and executor identity to ledger delivery IDs
parent: OOMPAH-192
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:31:43.705145Z'
updated_at: '2026-07-13T19:31:43.705145Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

