---
id: OOMPAH-304
type: bug
status: Open
priority: 1
title: Make Release Delivery show live delivery status consistently
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:frontend
assignee: null
created_at: '2026-07-21T16:20:03.352434Z'
updated_at: '2026-07-21T16:22:48.841061Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the Release Delivery UI so an item selected for delivery always shows its live status, progress, and result link.\n\nObserved reproduction (Trickle, target release/0.11): the commit-inventory endpoint reports commit 495d34a as state=in_review with delivery_id=rd_293edb9b53f44a22851c25e203d7651a and PR #303, while the Release Delivery backlog endpoint reports associated items as state=not_selected. The page therefore cannot reliably monitor work initiated from its own selection UI.\n\nImplementation requirements:\n- Establish one authoritative delivery-status resolution path shared by the backlog and commit-inventory endpoints, or document and implement an equivalent consistency guarantee.\n- For queued, preparing, in_progress, blocked/conflicted, in_review, delivered, failed, archived, and not_selected states, return the same state, delivery ID, PR URL, error/conflict summary, and updated timestamp from both endpoint shapes.\n- Update the Release Delivery page to refresh live status without a full browser reload and visibly link to the associated PR when one exists.\n- Preserve target-branch isolation: status for release/0.11 must not leak into another release branch.\n- Treat stale refresh/cache data explicitly in the UI rather than silently displaying not_selected.\n\nTests:\n- Regression fixture reproducing rd_293edb9b53f44a22851c25e203d7651a/PR #303-style in_review data verifies backlog and inventory responses agree.\n- Parameterized unit tests cover every delivery state and branch isolation.\n- Frontend test verifies an in_review item renders its state, delivery identifier, and PR link, then updates after a refresh.\n- Cache invalidation/refresh test verifies a newly queued delivery does not remain not_selected once ledger state is available.\n\nAcceptance criteria:\n- The Release Delivery page is a trustworthy progress monitor for all deliveries it creates.\n- No item with an active delivery or PR is displayed as not_selected.\n- Users can reach the active PR and see blocked/failed details from the page.\n- All relevant tests pass through the project Makefile test target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

