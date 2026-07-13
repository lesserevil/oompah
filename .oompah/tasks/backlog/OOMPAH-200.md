---
id: OOMPAH-200
type: task
status: Backlog
priority: 1
title: Replace the Release branches overlay with Release delivery UI
parent: OOMPAH-192
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:32:56.999746Z'
updated_at: '2026-07-13T19:32:56.999746Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md sections 2 and 6.

Replace the dashboard Release branches toolbar action and _rbi overlay with the project-scoped Release delivery overlay. Implement project selection, source metadata, release-line filters/columns, search, needs-delivery/all filter, pagination, accessible commit selection, multi-target confirmation, queue outcome feedback, and a per-row evidence drawer. Retain task/epic detail release controls but point them at ledger-backed data.

Acceptance criteria
- The toolbar opens Release delivery, defaults to the dashboard project filter, and never mixes projects.
- Each row renders a safe selectable source commit and text-labeled per-branch status; merge commits are informational and not selectable.
- Selecting commits and targets calls the new API, displays per-pair outcomes, clears only successful/skipped selection, and reloads page one.
- Delivered-by-cherry-pick and delivered-by-ancestry clearly show different evidence.
- Legacy Release branches overlay/state/helpers are removed; task/epic release controls still work.

Tests
- Add browser/template tests for project defaulting, filters, search, pagination, status rendering, selection/confirmation, outcome feedback, empty/error states, special-character escaping, keyboard Escape, and focus restoration.
- Add regression coverage that no untrusted API text is interpolated into inline event handlers.

Dependencies
- OOMPAH-196, OOMPAH-198, and OOMPAH-199.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

