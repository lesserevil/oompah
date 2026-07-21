---
id: OOMPAH-304
type: bug
status: Done
priority: 1
title: Make Release Delivery show live delivery status consistently
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:20:03.352434Z'
updated_at: '2026-07-21T17:10:39.857659Z'
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
author: oompah
created: 2026-07-21 17:10
---
Implementation complete. Changes across 5 files:

**Backend (release_delivery_refresh.py):** Added `invalidate(project_id, branch)` method to BacklogRefreshManager. Sets result_completed_at=0.0 (not None) so the TTL check always fires, forcing a fresh result on the next request.

**Backend (orchestrator.py):** Called invalidate() after cherry_pick_delivery() in _process_release_delivery_queue and after poll_delivery_pr() in _reconcile_delivery_pr_outcomes_sweep. Root cause fix: delivery executor never cleared the 5-minute BacklogRefreshManager cache, so backlog kept showing not_selected while commit-inventory showed in_review.

**Frontend (release_delivery.html):** (1) Modified _rdiRenderStatusCell to wrap badge+PR link in rdi-status-wrap, rendering an inline 'PR' anchor with aria-label and stopPropagation when cell.pr_url is set. (2) Added _rdiHasActiveDeliveries, _rdiStartDeliveryPoll, _rdiStopDeliveryPoll wired to a 30-second setInterval on open/in_progress/in_review/blocked states. (3) Added _rdiRecentlyQueuedIds Set tracking queued items; shows 'Queued — status updating…' hint when backlog cache still shows not_selected. (4) After queuing, calls _rdiForceRefresh() instead of _rdiLoadBacklog() to bypass cache immediately.

**Tests (test_release_delivery_page.py):** 35 new tests in TestLiveDeliveryStatusUI covering PR link rendering, poll lifecycle, pending hint, and wrap CSS.

**Tests (test_release_delivery_refresh.py):** 5 new tests in TestBacklogRefreshManagerInvalidate covering invalidation scenarios including regression for rd_293edb9b53f44a22851c25e203d7651a/PR #303.

**Tests (test_server_release_delivery_backlog.py):** 4 new tests in TestDeliveryStatusConsistency verifying state/delivery_id/pr_url consistency across all states and branch isolation.

Full test suite: 9989 passed, 36 skipped, 0 failed.
---
author: oompah
created: 2026-07-21 17:10
---
Verification: make test ran 9989 tests, 36 skipped, 0 failed. Branch OOMPAH-304 pushed to origin. All acceptance criteria met:
- No item with an active delivery is shown as not_selected (cache invalidated after executor/PR-poll runs)
- PR link appears inline in the status cell when a delivery has a PR URL
- 30-second auto-refresh active while open/in_progress/in_review/blocked deliveries exist
- 'Queued — status updating...' hint shown when cache has not caught up yet
- Branch isolation confirmed by TestDeliveryStatusConsistency.test_branch_isolation_different_branch_not_leaked
---
author: oompah
created: 2026-07-21 17:10
---
Fixed Release Delivery live status: backend cache invalidation after executor/PR-poll runs + frontend PR links, 30s auto-refresh poll, and stale-cache pending hint. 9989 tests pass.
---
<!-- COMMENTS:END -->
