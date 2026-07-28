---
id: OOMPAH-497
type: task
status: In Progress
priority: 2
title: Assign canonical ownership for overlapping Release Delivery UI tests
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:32.426575Z'
updated_at: '2026-07-28T16:09:28.786415Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 08a58dd5-cb91-470f-82aa-6a0afbb82743
oompah.work_branch: epic-OOMPAH-490
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 16:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:08
---
Agent failed: errored. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-28 16:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/fable]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 13s
- Log: OOMPAH-497__20260728T160757Z.jsonl
---
author: oompah
created: 2026-07-28 16:08
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 16:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:09
---
Understanding: Screening OOMPAH-497 for duplicates before any implementation. The task targets cross-file duplication among tests/test_dashboard_release_delivery_ui.py, tests/test_release_delivery_page.py, and tests/test_dashboard_release_addendums_ui.py to assign canonical ownership of page/navigation/accessibility contracts vs. dialog controls. I will search task records and project documentation for any prior equivalent work before proceeding.
---
<!-- COMMENTS:END -->
