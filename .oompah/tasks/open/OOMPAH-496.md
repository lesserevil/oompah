---
id: OOMPAH-496
type: chore
status: Open
priority: 2
title: Consolidate removed draft-epic and epic-strategy UI contracts
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:31.446905Z'
updated_at: '2026-07-28T14:35:34.131550Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Consolidate retired-interface regression coverage across `tests/test_dashboard_draft_epics.py`, `tests/test_draft_epic_swimlane.py`, `tests/test_draft_epic_badge.py`, `tests/test_draft_swimlane_toggle.py`, and `tests/test_projects_epic_strategy_ui.py`. Keep `test_dashboard_draft_epics.py` as the canonical draft-removal module: retain its four server/API tests, replace repeated static absence checks with one loop over well-named forbidden markers and one focused positive smoke test, then delete the other three draft-only files. In the epic-strategy file, replace per-CSS-class and per-variable absence cases with one forbidden-marker contract and one test scoped to the `saveProject()` function body. Include marker-specific assertion messages. Do not remove backend tests proving shared is the only supported epic strategy.

Tests

Run all five current files before the change and the surviving files afterward. Record collection counts. Ensure draft labels still behave as generic labels through the API and the projects page cannot submit `epic_strategy`. Run `make test` after the safety prerequisite.

Acceptance criteria

The same retired controls cannot silently return, the four API behavior cases remain, positive dashboard/project-page smoke coverage remains, declared tests across this area fall from 59 to no more than 12, and no deleted file owns unique production behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

