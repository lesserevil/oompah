---
id: OOMPAH-252
type: task
status: In Progress
priority: null
title: Move Release Delivery from dashboard dialog to a dedicated page
parent: null
children: []
blocked_by:
- OOMPAH-251
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T22:03:50.663411Z'
updated_at: '2026-07-19T23:48:21.444671Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 59b36ef0-6729-44a2-ae48-d2f362313b05
oompah.task_costs:
  total_input_tokens: 13
  total_output_tokens: 3240
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 13
      output_tokens: 3240
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 13
    output_tokens: 3240
    cost_usd: 0.0
    recorded_at: '2026-07-19T23:14:11.170765+00:00'
---
## Summary

Problem

Release Delivery currently opens as a dashboard dialog. It needs to support long-running discovery, progress, a retained prior result, task/epic candidate rows, selection, and merge status. A modal is too constrained for this workflow and prevents durable, shareable project-plus-release-branch navigation.

Required implementation

- Add a first-class Release Delivery page alongside the existing Review, Projects, and Providers pages. Add a persistent navigation entry named Release Delivery.
- The page must select a project and one configured supported release branch, persist that selection in the URL, and support direct links/bookmarks. Invalid or unavailable project/branch selections must show an actionable empty state.
- Move the existing candidate table, commit grouping, selection controls, queue action, and per-item delivery status from the dashboard dialog to this page without changing backend release-merge semantics.
- Integrate OOMPAH-251 refresh state: display the last completed candidate list while refresh runs; show progress phase, completed/total when known, elapsed time, error details, and retry. The page must not be blank or disabled without explanation.
- Remove the dashboard modal and its trigger once the dedicated page is functional. Preserve any useful dashboard summary as a link to the selected project Release Delivery page rather than duplicating the workflow.
- Ensure responsive layout and keyboard accessibility for the project selector, branch selector, candidate selection, progress status, and queue action.

Tests

- Dashboard/browser tests prove the navigation entry opens the dedicated page and the old modal is absent.
- Route tests cover direct page load, valid project/branch URL selection, invalid selection handling, and selection changes updating the URL.
- UI tests prove task/epic rows can be selected and queued from the page.
- UI tests cover initial loading, in-progress refresh with retained stale results, successful refresh, failure, and retry using the OOMPAH-251 API contract.
- Accessibility regression tests cover labelled controls, keyboard navigation, focus management, and status announcements.

Acceptance criteria

- Release Delivery is a dedicated navigable page, not a dialog.
- A user can bookmark/share a URL for Trickle plus release/0.11 and see its delivery state.
- The complete release-delivery workflow works from that page, including progress visibility and queueing selected items.
- The dashboard no longer contains a competing Release Delivery modal.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 23:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 23:12
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 23:13
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-252 is a distinct, original task. Duplicate screening reviewed all Release Delivery-related tasks (OOMPAH-201, OOMPAH-208, OOMPAH-216, OOMPAH-236, OOMPAH-237, OOMPAH-238, OOMPAH-239, OOMPAH-240, OOMPAH-241, OOMPAH-248, OOMPAH-249, OOMPAH-250, OOMPAH-251) and no existing task covers moving Release Delivery from a dashboard dialog to a dedicated navigable page with URL persistence, project/branch selectors, and removal of the modal.

2. Evidence reviewed:
   - OOMPAH-251 (Done): Implements the async refresh model and progress UI within the existing dashboard dialog. Its task file explicitly lists OOMPAH-252 as a separate dependent task: 'OOMPAH-252 (Open): Depends on OOMPAH-251; it moves Release Delivery to a dedicated page. Different scope.'
   - OOMPAH-236 (Merged): Replaced commit pagination with item-centric backlog — stays in the dialog, no navigation change.
   - OOMPAH-216 (Merged): Added reconciled branch status and retry controls — still in the dialog.
   - No other task addresses: dedicated page route, nav entry, URL-persisted project/branch selection, or removing the dashboard modal.

3. Remaining work / risks:
   - OOMPAH-251 is listed as a blocker and is in Done state, so the async backend API (GET /backlog/status, POST /backlog/refresh, stale-while-revalidate) is already available.
   - Key frontend files to examine: oompah/dashboard.html (existing RDI dialog markup + JS), oompah/server.py (routing), static JS/CSS if separated.
   - The implementation must preserve all existing Release Delivery semantics (candidate table, selection, queue action, per-item status) and integrate OOMPAH-251 progress API.
   - Accessibility (labelled controls, keyboard nav, focus management, status announcements) is a stated requirement.

4. Recommended next focus: frontend (dedicated Release Delivery page, navigation entry, URL routing, modal removal, OOMPAH-251 progress integration).
---
author: oompah
created: 2026-07-19 23:14
---
Agent completed successfully in 86s (3253 tokens)
---
author: oompah
created: 2026-07-19 23:14
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 24, Tool calls: 16
- Tokens: 13 in / 3.2K out [3.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 26s
- Log: OOMPAH-252__20260719T231251Z.jsonl
---
author: oompah
created: 2026-07-19 23:14
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-19 23:18
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 23:18
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-19 23:18
---
Understanding: Moving Release Delivery from dashboard dialog to a dedicated page. Plan: (1) Explore existing dashboard.html/server.py to understand current dialog structure; (2) Add /release-delivery route to server.py; (3) Create dedicated release_delivery.html page with project/branch selectors, candidate table, progress integration (OOMPAH-251 API), and accessibility; (4) Add nav entry; (5) Remove dashboard modal/trigger; (6) Write tests covering navigation, routing, UI, and accessibility; (7) Run make test.
---
author: oompah
created: 2026-07-19 23:22
---
Discovery: Found all relevant code. The RDI dialog in dashboard.html (lines 970-1400 CSS, 7148-8375 JS, 8595-8665 HTML) is the complete Release Delivery interface. OOMPAH-251 added async refresh model (release_delivery_refresh.py, /backlog/status, /backlog/refresh endpoints) and wired it into the dashboard dialog. The existing test_dashboard_release_delivery_ui.py covers the dialog. Plan: (1) Create oompah/templates/release_delivery.html — full page with nav, URL-based project+branch selection, complete RDI workflow, OOMPAH-251 progress integration; (2) Add /release-delivery route to server.py; (3) Replace dashboard 'Release delivery' button with nav link; (4) Remove overlay HTML/CSS/JS from dashboard.html; (5) Update test_dashboard_release_delivery_ui.py to verify modal is absent; (6) Write tests/test_release_delivery_page.py for route, nav, URL persistence, routing, UI, accessibility.
---
author: oompah
created: 2026-07-19 23:47
---
Implementation complete. Changes:

**release_delivery.html** (new, ~1730 lines): Full dedicated Release Delivery page with toolbar, project/branch selectors, filter/search controls, OOMPAH-251 progress banner, candidate table, action bar, evidence drawer. URL persistence via _rdiReadUrl()/_rdiPushUrl() + history.replaceState. _rdiRefresh() wrapper delegates to _rdiForceRefresh(). pagehide listener stops polling on navigation. No rdi-overlay div — this is a first-class page, not a dialog.

**server.py**: Added GET /release-delivery route serving release_delivery.html.

**dashboard.html**: Removed RDI overlay HTML (75 lines), CSS (424 lines), JS (1230 lines). Nav button now navigates to /release-delivery instead of opening a dialog.

**test_dashboard_release_delivery_ui.py**: Updated tests to use _load_release_delivery_*() helpers; fixed overlay-specific tests to reflect page structure; updated accessibility tests to check page-level attributes; fixed TestFunctionDefinitions and TestAsyncRefreshProgressFunctions.

**test_release_delivery_page.py** (new, 74 tests): Route, navigation, page structure, URL persistence, bootstrap, OOMPAH-251 progress integration, empty states, and accessibility.
---
author: oompah
created: 2026-07-19 23:48
---
Completion: OOMPAH-252 delivered.

Release Delivery is now a dedicated navigable page at /release-delivery, not a dashboard dialog.

What was delivered:
- GET /release-delivery route serving oompah/templates/release_delivery.html
- Full page with project/branch selectors, filter/search controls, OOMPAH-251 progress banner (phase, progress bar, elapsed, retry), candidate table, action bar, evidence drawer
- URL persistence: ?project=<id>&branch=release/0.11 — bookmarkable, shareable, direct-link-safe
- _rdiReadUrl() / _rdiPushUrl() + history.replaceState for URL sync on every selection change
- Stale-while-revalidate: prior results stay visible while background refresh runs
- pagehide listener stops polling timer when user navigates away
- Dashboard nav button replaced: onclick navigates to /release-delivery instead of opening modal
- rdi-overlay HTML, CSS, JS removed from dashboard.html
- 74 new tests in test_release_delivery_page.py; test_dashboard_release_delivery_ui.py updated
- All 9410 tests pass (make test green)
---
<!-- COMMENTS:END -->
