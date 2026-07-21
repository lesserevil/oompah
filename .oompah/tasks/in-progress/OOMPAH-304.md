---
id: OOMPAH-304
type: bug
status: In Progress
priority: 1
title: Make Release Delivery show live delivery status consistently
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:20:03.352434Z'
updated_at: '2026-07-21T16:46:06.425141Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 4c4faa9f-3c9c-4cd5-b4a1-4a0b5ab43697
---
## Summary

Fix the Release Delivery UI so an item selected for delivery always shows its live status, progress, and result link.\n\nObserved reproduction (Trickle, target release/0.11): the commit-inventory endpoint reports commit 495d34a as state=in_review with delivery_id=rd_293edb9b53f44a22851c25e203d7651a and PR #303, while the Release Delivery backlog endpoint reports associated items as state=not_selected. The page therefore cannot reliably monitor work initiated from its own selection UI.\n\nImplementation requirements:\n- Establish one authoritative delivery-status resolution path shared by the backlog and commit-inventory endpoints, or document and implement an equivalent consistency guarantee.\n- For queued, preparing, in_progress, blocked/conflicted, in_review, delivered, failed, archived, and not_selected states, return the same state, delivery ID, PR URL, error/conflict summary, and updated timestamp from both endpoint shapes.\n- Update the Release Delivery page to refresh live status without a full browser reload and visibly link to the associated PR when one exists.\n- Preserve target-branch isolation: status for release/0.11 must not leak into another release branch.\n- Treat stale refresh/cache data explicitly in the UI rather than silently displaying not_selected.\n\nTests:\n- Regression fixture reproducing rd_293edb9b53f44a22851c25e203d7651a/PR #303-style in_review data verifies backlog and inventory responses agree.\n- Parameterized unit tests cover every delivery state and branch isolation.\n- Frontend test verifies an in_review item renders its state, delivery identifier, and PR link, then updates after a refresh.\n- Cache invalidation/refresh test verifies a newly queued delivery does not remain not_selected once ledger state is available.\n\nAcceptance criteria:\n- The Release Delivery page is a trustworthy progress monitor for all deliveries it creates.\n- No item with an active delivery or PR is displayed as not_selected.\n- Users can reach the active PR and see blocked/failed details from the page.\n- All relevant tests pass through the project Makefile test target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:31
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 16:31
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 16:46
---
**Understanding**: Root cause identified — the Release Delivery backlog endpoint uses BacklogRefreshManager which caches computed BacklogResult objects for 5 minutes (DEFAULT_RESULT_TTL_S=300). When a delivery executor updates status to IN_REVIEW (with PR), the commit-inventory reads the ledger fresh and shows the correct state, but the backlog serves the cached (pre-delivery) result showing not_selected. Two orthogonal fixes are needed: (1) Backend: delivery executor/poller must trigger backlog cache invalidation on status change; (2) Frontend: show PR links inline in the table, add delivery-status-aware auto-refresh when active deliveries exist, and treat stale delivery status explicitly rather than silently.

Plan: (1) Add PR link to table status cells when cell.pr_url is present; (2) Add _rdiStartDeliveryPoll/_rdiStopDeliveryPoll that auto-refresh every 30s when in_progress/in_review/blocked/open deliveries exist; (3) Track recently-queued items and show 'status updating' indicator when they still show not_selected; (4) After queuing, call _rdiForceRefresh() to trigger immediate backlog refresh; (5) Stop delivery poll on pagehide; (6) Add CSS for .rdi-pr-link and .rdi-delivery-pending; (7) Add frontend tests; (8) Add backend cache-invalidation fix in executor/poller + regression tests.
---
<!-- COMMENTS:END -->
