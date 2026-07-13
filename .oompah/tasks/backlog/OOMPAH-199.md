---
id: OOMPAH-199
type: task
status: Backlog
priority: 1
title: Add commit-selection release delivery queue API
parent: OOMPAH-192
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:32:53.860350Z'
updated_at: '2026-07-13T19:32:53.860350Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md section 4.2 POST contract.

Implement POST /api/v1/projects/{project_id}/release-delivery/commits. It accepts a source-head snapshot, ordered full source SHAs, target release branches, and an Idempotency-Key. Revalidate source reachability/non-merge eligibility and branch availability server-side, append exact immutable delivery bundles under the ledger lock, then wake the existing queue only after persistence.

Acceptance criteria
- Creates one ordered delivery bundle per eligible target branch and never creates an ordinary task.
- Rejects a changed source HEAD, invalid/unreachable/merge SHA, unavailable branch, missing idempotency key, and malformed payload before writing.
- Returns explicit created, already_active, already_delivered, and invalid per-pair outcomes without duplicate deliveries.
- Replaying the same idempotency key returns the original outcome and makes no additional ledger write.

Tests
- Server tests cover one/many commits, one/many targets, atomic validation failure, duplicate active/merged pairs, archived reapproval, queue wake-up after persistence, and idempotency replay.
- Test the queued source order reaches the executor unchanged.

Dependencies
- OOMPAH-195 and OOMPAH-198.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

