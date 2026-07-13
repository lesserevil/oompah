---
id: OOMPAH-200
type: task
status: In Progress
priority: 1
title: Replace the Release branches overlay with Release delivery UI
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-196
- OOMPAH-198
- OOMPAH-199
labels: []
assignee: null
created_at: '2026-07-13T19:32:56.999746Z'
updated_at: '2026-07-13T22:36:55.449191Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5fa5f4e4-6a61-409e-bedf-1b2548419b53
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 22:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 22:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 22:35
---
Understanding: As the Duplicate Investigator, I need to determine whether OOMPAH-200 ('Replace the Release branches overlay with Release delivery UI') is a duplicate of any existing issue before proceeding with implementation. I will search for similar tasks covering: release delivery UI, release branches overlay replacement, commit inventory, and related topics. Plan reference is plans/release-delivery-commit-inventory.md sections 2 and 6. Will report findings shortly.
---
author: oompah
created: 2026-07-13 22:36
---
Duplicate investigation complete: OOMPAH-200 is unique. The sibling tasks in the OOMPAH-192 epic cover: ledger schema (193), migration (194), queue/executor refactoring (195), task/epic compat (196), CommitInventoryService (197), GET inventory API (198), POST queue API (199), docs/deprecation (201), and e2e (202). No archived, done, or open task replaces the dashboard Release branches overlay/_rbi with a UI. All blockers (OOMPAH-196, OOMPAH-198, OOMPAH-199) are Done. Proceeding with implementation: replacing the _rbi overlay and toolbar action with the Release delivery overlay (sections 2 and 6 of plans/release-delivery-commit-inventory.md).
---
<!-- COMMENTS:END -->
