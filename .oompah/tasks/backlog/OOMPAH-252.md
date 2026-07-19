---
id: OOMPAH-252
type: task
status: Backlog
priority: null
title: Move Release Delivery from dashboard dialog to a dedicated page
parent: null
children: []
blocked_by:
- OOMPAH-251
labels: []
assignee: null
created_at: '2026-07-19T22:03:50.663411Z'
updated_at: '2026-07-19T22:03:53.060199Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

