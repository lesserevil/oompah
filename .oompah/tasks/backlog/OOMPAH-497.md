---
id: OOMPAH-497
type: task
status: Backlog
priority: 2
title: Assign canonical ownership for overlapping Release Delivery UI tests
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:32.426575Z'
updated_at: '2026-07-28T13:53:57.039082Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Map and remove cross-file duplication among `tests/test_dashboard_release_delivery_ui.py`, `tests/test_release_delivery_page.py`, and `tests/test_dashboard_release_addendums_ui.py`. Treat `test_release_delivery_page.py` as the owner of dedicated-page navigation, page structure, URL state, bootstrap, accessibility, and live-status contracts. Treat `test_dashboard_release_addendums_ui.py` as the owner of add-release-branches dialog controls. Remove the same-named or equivalent copies from `test_dashboard_release_delivery_ui.py`, including the retained-controls assertions already covered by the addendums suite. Update stale module/class docstrings that still call the dedicated page an overlay. Do not yet collapse unique backlog rendering, selection, queuing, status, drawer, XSS, or refresh behavior; that belongs to the dependent task.

Tests

Create a short contract-ownership table in a comment at the top of the surviving legacy-named file, listing each category and canonical test module. Run all three files before and after and record collection counts. Search for duplicate test names across these files and justify any remaining collision. Run `make test` after safety isolation.

Acceptance criteria

Each page/dialog contract has one clear owner, at least the 12 same-named page contracts and five exact retained-control duplicates are removed or merged, module descriptions match the dedicated-page architecture, and all three focused suites pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

